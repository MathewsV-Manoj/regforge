"""RegForge command line interface.

Deliberately built on argparse rather than a CLI framework. This is a tool
engineers will `pip install` into an existing embedded toolchain, and every
transitive dependency is a reason for it not to get installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .codegen.c_driver import generate_driver_header, generate_driver_source
from .codegen.c_header import generate_regs_header
from .codegen.c_tests import generate_regs_test
from .corpus import Corpus, slug
from .models import DeviceRecord
from .validate import Severity, coverage_score, is_clean, summarise, validate_device


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _parse_pages(spec: str) -> list[int]:
    """Parse a 1-based page spec like '24-31,40' into 0-based indices."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, _, hi_s = part.partition("-")
            lo, hi = int(lo_s), int(hi_s)
            if lo > hi:
                raise ValueError(f"page range {part!r} runs backwards")
            out.update(range(lo, hi + 1))
        else:
            out.add(int(part))
    if any(p < 1 for p in out):
        raise ValueError("page numbers are 1-based")
    return sorted(p - 1 for p in out)


def _print_findings(findings, *, show_info: bool) -> None:
    for f in findings:
        if f.severity is Severity.INFO and not show_info:
            continue
        print(f"  {f}")


def _report(record: DeviceRecord, *, show_info: bool = False) -> bool:
    """Print a validation report. Returns True when the map is clean."""
    findings = validate_device(record.device)
    counts = summarise(findings)
    clean = is_clean(findings)

    print(f"\n{record.device.part_number} ({record.device.manufacturer})")
    print(f"  registers: {len(record.device.registers)}   bit coverage: {coverage_score(record.device) * 100:.0f}%")

    if findings:
        print()
        _print_findings(findings, show_info=show_info)

    print(
        f"\n  {counts['errors']} error(s), {counts['warnings']} warning(s), {counts['info']} note(s)"
        + ("" if show_info else "   (use --verbose to see notes)")
    )
    print("  status: " + ("PASS" if clean else "FAIL -- do not generate code from this map"))
    return clean


def _write_outputs(record: DeviceRecord, out_dir: Path, *, driver: bool, tests: bool = False) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = slug(record.device.part_number).replace("-", "_")
    written: list[Path] = []

    regs = out_dir / f"{stem}_regs.h"
    regs.write_text(generate_regs_header(record), encoding="utf-8")
    written.append(regs)

    if tests:
        test = out_dir / f"{stem}_regs_test.c"
        test.write_text(generate_regs_test(record), encoding="utf-8")
        written.append(test)

    if driver:
        hdr = out_dir / f"{stem}.h"
        hdr.write_text(generate_driver_header(record), encoding="utf-8")
        written.append(hdr)

        src = out_dir / f"{stem}.c"
        src.write_text(generate_driver_source(record), encoding="utf-8")
        written.append(src)

    return written


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    """Show which pages RegForge thinks hold the register map. Costs nothing."""
    from .pdf import find_register_pages, load_pdf, score_page

    pdf = load_pdf(args.pdf)
    selected = set(find_register_pages(pdf, max_pages=args.max_pages))

    print(f"{pdf.filename}: {pdf.page_count} pages, sha256 {pdf.sha256[:16]}...")
    print(f"\n{'page':>6}  {'score':>6}  {'hex':>5}  {'bits':>5}  selected")
    scored = [(i, score_page(t)) for i, t in enumerate(pdf.page_texts)]
    shown = 0
    for i, ps in sorted(scored, key=lambda kv: kv[1].score, reverse=True):
        if ps.score <= 0 and i not in selected:
            continue
        if shown >= args.top and i not in selected:
            continue
        mark = "  <--" if i in selected else ""
        print(f"{i + 1:>6}  {ps.score:>6.2f}  {ps.hex_addrs:>5}  {ps.bit_ranges:>5}{mark}")
        shown += 1

    pages_1b = sorted(p + 1 for p in selected)
    print(f"\nselected {len(pages_1b)} page(s): {_compact_ranges(pages_1b)}")
    print(f"extract with:  regforge extract {args.pdf} --pages {_compact_ranges(pages_1b)}")
    return 0


def _compact_ranges(pages: list[int]) -> str:
    if not pages:
        return ""
    parts, start, prev = [], pages[0], pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
            continue
        parts.append(f"{start}-{prev}" if start != prev else f"{start}")
        start = prev = p
    parts.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ",".join(parts)


def cmd_extract(args: argparse.Namespace) -> int:
    from .extract import extract_from_pdf

    pages = _parse_pages(args.pages) if args.pages else None

    try:
        result = extract_from_pdf(
            args.pdf,
            model=args.model,
            part_hint=args.part,
            pages=pages,
            chunk_size=args.chunk_size,
            max_pages=args.max_pages,
        )
    except Exception as exc:
        _err(str(exc))
        return 1

    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)

    print(f"\nextracted from pages {_compact_ranges([p + 1 for p in result.pages_used])}")
    print(result.ledger.report())

    clean = _report(result.record, show_info=args.verbose)

    if not args.no_save:
        corpus = Corpus(args.corpus)
        path = corpus.save(result.record)
        print(f"\nsaved -> {path}")

    if args.out:
        if not clean and not args.force:
            _err("map has errors; not generating code (use --force to override)")
            return 2
        written = _write_outputs(result.record, Path(args.out), driver=args.driver, tests=args.tests)
        print("generated:")
        for p in written:
            print(f"  {p}")

    return 0 if clean else 2


def cmd_gen(args: argparse.Namespace) -> int:
    """Generate code from the corpus. No model call, no cost."""
    corpus = Corpus(args.corpus)

    if args.file:
        record = corpus.load_path(Path(args.file))
    else:
        record = corpus.get(args.part)
        if record is None:
            _err(f"{args.part!r} is not in the corpus at {corpus.root}")
            matches = corpus.find(args.part)
            if matches:
                print("did you mean:", file=sys.stderr)
                for m in matches[:5]:
                    print(f"  {m.part_number} ({m.manufacturer})", file=sys.stderr)
            else:
                print(f"extract it first:  regforge extract <datasheet.pdf> --part {args.part}", file=sys.stderr)
            return 1

    clean = _report(record, show_info=args.verbose)
    if not clean and not args.force:
        _err("map has errors; not generating code (use --force to override)")
        return 2

    written = _write_outputs(record, Path(args.out), driver=args.driver, tests=args.tests)
    print("\ngenerated:")
    for p in written:
        print(f"  {p}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    corpus = Corpus(args.corpus)
    record = corpus.load_path(Path(args.file)) if args.file else corpus.get(args.part)
    if record is None:
        _err(f"{args.part!r} is not in the corpus at {corpus.root}")
        return 1
    return 0 if _report(record, show_info=args.verbose) else 2


def cmd_list(args: argparse.Namespace) -> int:
    corpus = Corpus(args.corpus)
    entries = corpus.find(args.query) if args.query else corpus.list_all()
    if not entries:
        print(f"corpus at {corpus.root} is empty")
        return 0
    print(f"{'part':<20} {'manufacturer':<24} {'regs':>5}  verified")
    for e in entries:
        print(f"{e.part_number:<20} {e.manufacturer:<24} {e.register_count:>5}  {'yes' if e.verified else 'no'}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    corpus = Corpus(args.corpus)
    record = corpus.get(args.part)
    if record is None:
        _err(f"{args.part!r} is not in the corpus")
        return 1
    if not is_clean(validate_device(record.device)) and not args.force:
        _err("map still has errors; fix them before marking it verified (or use --force)")
        return 2
    path = corpus.mark_verified(args.part, by=args.by, notes=args.notes)
    print(f"marked verified by {args.by} -> {path}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    corpus = Corpus(args.corpus)
    s = corpus.stats()
    print(f"corpus: {corpus.root}")
    print(f"  parts         {s['parts']}")
    print(f"  verified      {s['verified']} ({s['verified_pct']}%)")
    print(f"  manufacturers {s['manufacturers']}")
    print(f"  registers     {s['registers']}")
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    # Shared flags, accepted either before or after the subcommand. argparse
    # would otherwise clobber a leading `-v` with the subparser's default, so
    # the parent suppresses its defaults and only the top level supplies them.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    common.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    p = argparse.ArgumentParser(
        prog="regforge",
        description="Turn a datasheet into a verified register map and driver code.",
    )
    p.add_argument("--version", action="version", version=f"regforge {__version__}")
    p.add_argument("--corpus", default=None, help="corpus directory (default: ./corpus or ~/.regforge/corpus)")
    p.add_argument("-v", "--verbose", action="store_true", help="show informational findings too")

    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser(
        "scan", parents=[common], help="show which pages look like a register map (free, no API call)"
    )
    s.add_argument("pdf")
    s.add_argument("--max-pages", type=int, default=40)
    s.add_argument("--top", type=int, default=25, help="how many non-selected pages to list")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("extract", parents=[common], help="extract a register map from a datasheet PDF (calls the API)")
    s.add_argument("pdf")
    s.add_argument("--part", default=None, help="part number hint, e.g. BME280")
    s.add_argument("--pages", default=None, help="1-based page spec, e.g. 24-31,40")
    s.add_argument("--model", default=None, help="extraction model id")
    s.add_argument("--chunk-size", type=int, default=8, help="pages per extraction pass")
    s.add_argument("--max-pages", type=int, default=40)
    s.add_argument("--out", default=None, help="also generate code into this directory")
    s.add_argument("--driver", action="store_true", help="generate the driver skeleton as well")
    s.add_argument("--tests", action="store_true", help="generate compile-time assertions for the bit math")
    s.add_argument("--no-save", action="store_true", help="do not write to the corpus")
    s.add_argument("--force", action="store_true", help="generate code even if validation fails")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("gen", parents=[common], help="generate code from a corpus entry (free, no API call)")
    s.add_argument("part", nargs="?", default=None)
    s.add_argument("--file", default=None, help="generate from a specific JSON record instead")
    s.add_argument("--out", default="out", help="output directory (default: out)")
    s.add_argument("--driver", action="store_true", help="generate the driver skeleton as well")
    s.add_argument("--tests", action="store_true", help="generate compile-time assertions for the bit math")
    s.add_argument("--force", action="store_true", help="generate even if validation fails")
    s.set_defaults(func=cmd_gen)

    s = sub.add_parser("check", parents=[common], help="validate a corpus entry")
    s.add_argument("part", nargs="?", default=None)
    s.add_argument("--file", default=None)
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("list", parents=[common], help="list corpus entries")
    s.add_argument("query", nargs="?", default=None)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("verify", parents=[common], help="mark a corpus entry as human-verified")
    s.add_argument("part")
    s.add_argument("--by", required=True, help="who checked it")
    s.add_argument("--notes", default=None)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("stats", parents=[common], help="corpus summary")
    s.set_defaults(func=cmd_stats)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "extract" and args.model is None:
        from .costs import DEFAULT_EXTRACT_MODEL

        args.model = DEFAULT_EXTRACT_MODEL

    if args.command in {"gen", "check"} and not args.part and not args.file:
        parser.error("give a part number or --file")

    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        _err(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
