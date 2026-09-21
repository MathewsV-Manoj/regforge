"""The verified register-map corpus.

This is the asset. Extraction is a cost; the corpus is what the cost buys. The
first person to ask for a BME280 pays for a model pass, and everyone after that
is served from here for nothing. That asymmetry is the entire unit-economics
argument, so the store is deliberately boring: plain JSON on disk, stable key
ordering, human-diffable, git-friendly.

The corpus is layered, and the layering is what makes `pip install regforge &&
regforge gen BME280` work on a machine that has never run an extraction:

    writable  ./corpus, or $REGFORGE_CORPUS, or ~/.regforge/corpus
              everything you extract or verify yourself. Always written here.

    bundled   regforge/corpus_data, shipped inside the wheel
              read-only, every part the project has published.

Lookups check writable first so your own copy of a part always wins over the
shipped one -- if you have verified a map against your own revision of a
datasheet, that is the map you want generated.

Layout within each layer:

    bosch-sensortec/bme280.json
    invensense/mpu6050.json

Records are keyed by part number, not by source file, because two datasheet
revisions describe the same chip and should converge on one entry.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .models import DeviceRecord

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def bundled_corpus_dir() -> Path:
    """The read-only corpus shipped inside the installed package.

    Present in a built wheel; absent in a bare source checkout, where the
    repository's own ./corpus is picked up as the writable layer instead.
    """
    return Path(__file__).resolve().parent / "corpus_data"


def default_corpus_dir() -> Path:
    """Where writes go, most specific source first."""
    env = os.environ.get("REGFORGE_CORPUS")
    if env:
        return Path(env).expanduser()
    local = Path.cwd() / "corpus"
    if local.is_dir():
        return local
    return Path.home() / ".regforge" / "corpus"


def slug(text: str) -> str:
    """Filesystem-safe, stable, lowercase key."""
    s = _SLUG_STRIP.sub("-", (text or "").strip().lower()).strip("-")
    return s or "unknown"


@dataclass
class CorpusEntry:
    part_number: str
    manufacturer: str
    path: Path
    register_count: int
    verified: bool
    bundled: bool = False


class Corpus:
    def __init__(self, root: Path | str | None = None, *, include_bundled: bool = True) -> None:
        self.root = Path(root) if root is not None else default_corpus_dir()
        self.include_bundled = include_bundled

    @property
    def search_roots(self) -> list[Path]:
        """Read layers, highest precedence first."""
        roots = [self.root]
        if self.include_bundled:
            bundled = bundled_corpus_dir()
            # resolve() so an editable install pointing at the repo does not
            # list the same directory twice.
            if bundled.is_dir() and bundled.resolve() != self.root.resolve():
                roots.append(bundled)
        return roots

    # -- paths ---------------------------------------------------------------

    def path_for(self, manufacturer: str, part_number: str) -> Path:
        return self.root / slug(manufacturer) / f"{slug(part_number)}.json"

    # -- writing -------------------------------------------------------------

    def save(self, record: DeviceRecord) -> Path:
        """Write to the writable layer. Never touches the bundled corpus."""
        path = self.path_for(record.device.manufacturer, record.device.part_number)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = record.model_dump(mode="json")
        # sort_keys keeps diffs meaningful when a map is re-extracted.
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    # -- reading -------------------------------------------------------------

    def load_path(self, path: Path) -> DeviceRecord:
        return DeviceRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def get(self, part_number: str, manufacturer: str | None = None) -> DeviceRecord | None:
        """Exact lookup across every layer, writable first."""
        target = slug(part_number)

        for root in self.search_roots:
            if manufacturer:
                path = root / slug(manufacturer) / f"{target}.json"
                if path.is_file():
                    return self.load_path(path)
                continue

            if not root.is_dir():
                continue
            for path in sorted(root.glob(f"*/{target}.json")):
                return self.load_path(path)

        return None

    def find(self, query: str) -> list[CorpusEntry]:
        """Substring match over part numbers, for `regforge list <query>`."""
        q = slug(query)
        return [e for e in self.list_all() if q in slug(e.part_number)]

    def list_all(self) -> list[CorpusEntry]:
        """Every visible part. A writable entry shadows a bundled one."""
        seen: dict[str, CorpusEntry] = {}

        for root in self.search_roots:
            if not root.is_dir():
                continue
            bundled = root != self.root
            for path in sorted(root.glob("*/*.json")):
                try:
                    rec = self.load_path(path)
                except Exception:
                    # A corrupt or hand-edited file should not take down a listing.
                    continue
                key = slug(rec.device.part_number)
                if key in seen:
                    continue  # earlier layer wins
                seen[key] = CorpusEntry(
                    part_number=rec.device.part_number,
                    manufacturer=rec.device.manufacturer,
                    path=path,
                    register_count=len(rec.device.registers),
                    verified=rec.provenance.verified,
                    bundled=bundled,
                )

        return sorted(seen.values(), key=lambda e: (slug(e.manufacturer), slug(e.part_number)))

    # -- bookkeeping ---------------------------------------------------------

    def mark_verified(self, part_number: str, by: str, notes: str | None = None) -> Path | None:
        """Mark a part verified.

        A bundled part is copied into the writable layer first, so verifying
        something that shipped with the package does not try to write inside
        site-packages.
        """
        rec = self.get(part_number)
        if rec is None:
            return None
        rec.provenance.verified = True
        rec.provenance.verified_by = by
        if notes:
            rec.provenance.notes = notes
        return self.save(rec)

    def stats(self) -> dict[str, int | float]:
        entries = self.list_all()
        verified = sum(1 for e in entries if e.verified)
        registers = sum(e.register_count for e in entries)
        return {
            "parts": len(entries),
            "verified": verified,
            "bundled": sum(1 for e in entries if e.bundled),
            "local": sum(1 for e in entries if not e.bundled),
            "manufacturers": len({slug(e.manufacturer) for e in entries}),
            "registers": registers,
            "verified_pct": round(100.0 * verified / len(entries), 1) if entries else 0.0,
        }


__all__ = ["Corpus", "CorpusEntry", "default_corpus_dir", "bundled_corpus_dir", "slug"]
