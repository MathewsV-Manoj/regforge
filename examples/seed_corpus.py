"""Build the shipped corpus from the hand-authored seeds.

Every map is validated before it is written. A seed that fails validation is
refused rather than saved, because a corpus that ships broken maps is worse
than an empty one -- it spends the user's trust instead of earning it.

    python examples/seed_corpus.py            # write to ./corpus
    python examples/seed_corpus.py --check    # validate only, write nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "examples"))

from regforge.corpus import Corpus  # noqa: E402
from regforge.validate import (  # noqa: E402
    Severity,
    coverage_score,
    is_clean,
    summarise,
    validate_device,
)
from seeds import SEEDS  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate without writing")
    ap.add_argument("--corpus", default=str(REPO / "corpus"))
    ap.add_argument("part", nargs="?", help="seed a single part instead of all of them")
    args = ap.parse_args(argv)

    if args.part and args.part.upper() not in SEEDS:
        print(f"error: no seed named {args.part!r}. Known: {', '.join(sorted(SEEDS))}", file=sys.stderr)
        return 1

    corpus = Corpus(args.corpus, include_bundled=False)
    selected = {args.part.upper(): SEEDS[args.part.upper()]} if args.part else SEEDS

    failures = 0
    total_registers = 0

    print(f"{'part':<12} {'regs':>5} {'cover':>6} {'err':>4} {'warn':>5}  status")
    print("-" * 52)

    for part, build in sorted(selected.items()):
        record = build()
        findings = validate_device(record.device)
        counts = summarise(findings)
        clean = is_clean(findings)
        total_registers += len(record.device.registers)

        print(
            f"{part:<12} {len(record.device.registers):>5} "
            f"{coverage_score(record.device) * 100:>5.0f}% "
            f"{counts['errors']:>4} {counts['warnings']:>5}  "
            f"{'ok' if clean else 'FAILED'}"
        )

        if not clean:
            failures += 1
            for f in findings:
                if f.severity is Severity.ERROR:
                    print(f"    {f}", file=sys.stderr)
            continue

        if not args.check:
            corpus.save(record)

    print("-" * 52)
    print(f"{len(selected)} part(s), {total_registers} registers, {failures} failed")

    if failures:
        print("\nrefusing to ship a corpus with validation errors", file=sys.stderr)
        return 1

    if not args.check:
        print(f"written to {corpus.root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
