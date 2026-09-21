"""The verified register-map corpus.

This is the asset. Extraction is a cost; the corpus is what the cost buys. The
first person to ask for a BME280 pays for a model pass, and everyone after that
is served from here for nothing. That asymmetry is the entire unit-economics
argument, so the store is deliberately boring: plain JSON on disk, stable key
ordering, human-diffable, git-friendly.

Layout:

    corpus/
      bosch-sensortec/
        bme280.json
      invensense/
        mpu6050.json

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


def default_corpus_dir() -> Path:
    """Where the corpus lives, most specific source first."""
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


class Corpus:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else default_corpus_dir()

    # -- paths ---------------------------------------------------------------

    def path_for(self, manufacturer: str, part_number: str) -> Path:
        return self.root / slug(manufacturer) / f"{slug(part_number)}.json"

    # -- writing -------------------------------------------------------------

    def save(self, record: DeviceRecord) -> Path:
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
        """Exact lookup. Searches every manufacturer when none is given."""
        target = slug(part_number)

        if manufacturer:
            path = self.path_for(manufacturer, part_number)
            return self.load_path(path) if path.is_file() else None

        if not self.root.is_dir():
            return None
        for path in sorted(self.root.glob(f"*/{target}.json")):
            return self.load_path(path)
        return None

    def find(self, query: str) -> list[CorpusEntry]:
        """Substring match over part numbers, for `regforge search`."""
        q = slug(query)
        return [e for e in self.list_all() if q in slug(e.part_number)]

    def list_all(self) -> list[CorpusEntry]:
        entries: list[CorpusEntry] = []
        if not self.root.is_dir():
            return entries
        for path in sorted(self.root.glob("*/*.json")):
            try:
                rec = self.load_path(path)
            except Exception:
                # A corrupt or hand-edited file should not take down a listing.
                continue
            entries.append(
                CorpusEntry(
                    part_number=rec.device.part_number,
                    manufacturer=rec.device.manufacturer,
                    path=path,
                    register_count=len(rec.device.registers),
                    verified=rec.provenance.verified,
                )
            )
        return entries

    # -- bookkeeping ---------------------------------------------------------

    def mark_verified(self, part_number: str, by: str, notes: str | None = None) -> Path | None:
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
            "manufacturers": len({slug(e.manufacturer) for e in entries}),
            "registers": registers,
            "verified_pct": round(100.0 * verified / len(entries), 1) if entries else 0.0,
        }


__all__ = ["Corpus", "CorpusEntry", "default_corpus_dir", "slug"]
