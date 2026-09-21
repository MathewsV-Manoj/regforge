"""Layered-corpus behaviour.

The bug these exist to prevent: the wheel shipped with no corpus in it, so
`pip install regforge && regforge gen BME280` failed for every user who had not
cloned the repository. A corpus nobody receives is not an asset.
"""

from __future__ import annotations

import json

import pytest
from conftest import device, register

from regforge.corpus import Corpus, bundled_corpus_dir
from regforge.models import DeviceRecord, Provenance


def write_record(root, part, manufacturer="Acme Semiconductor", *, verified=False, regs=1):
    rec = DeviceRecord(
        device=device(
            [register(f"R{i}", i) for i in range(regs)],
            part_number=part,
            manufacturer=manufacturer,
        ),
        provenance=Provenance(regforge_version="test", verified=verified),
    )
    c = Corpus(root, include_bundled=False)
    return c.save(rec)


@pytest.fixture
def layers(tmp_path, monkeypatch):
    """A writable layer and a fake bundled layer."""
    writable = tmp_path / "writable"
    bundled = tmp_path / "bundled"
    writable.mkdir()
    bundled.mkdir()
    monkeypatch.setattr("regforge.corpus.bundled_corpus_dir", lambda: bundled)
    return writable, bundled


class TestLookupPrecedence:
    def test_bundled_part_is_found_with_an_empty_writable_layer(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")

        rec = Corpus(writable).get("BME280")
        assert rec is not None, "this is the pip-install case; it must work"
        assert rec.device.part_number == "BME280"

    def test_writable_copy_shadows_the_bundled_one(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec", regs=1)
        write_record(writable, "BME280", "Bosch Sensortec", regs=5)

        rec = Corpus(writable).get("BME280")
        assert len(rec.device.registers) == 5, "your own verified map must win"

    def test_missing_everywhere_returns_none(self, layers):
        writable, _ = layers
        assert Corpus(writable).get("NOSUCHPART") is None

    def test_bundled_can_be_disabled(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")
        assert Corpus(writable, include_bundled=False).get("BME280") is None


class TestListing:
    def test_lists_across_both_layers(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")
        write_record(writable, "MPU6050", "InvenSense")

        parts = {e.part_number for e in Corpus(writable).list_all()}
        assert parts == {"BME280", "MPU6050"}

    def test_source_is_reported(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")
        write_record(writable, "MPU6050", "InvenSense")

        by_part = {e.part_number: e for e in Corpus(writable).list_all()}
        assert by_part["BME280"].bundled is True
        assert by_part["MPU6050"].bundled is False

    def test_shadowed_part_appears_once(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")
        write_record(writable, "BME280", "Bosch Sensortec")

        entries = Corpus(writable).list_all()
        assert len(entries) == 1
        assert entries[0].bundled is False

    def test_stats_split_local_and_bundled(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")
        write_record(bundled, "MPU6050", "InvenSense")
        write_record(writable, "ADS1115", "Texas Instruments")

        s = Corpus(writable).stats()
        assert s["parts"] == 3
        assert s["bundled"] == 2
        assert s["local"] == 1

    def test_find_searches_both_layers(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")
        assert [e.part_number for e in Corpus(writable).find("bme")] == ["BME280"]


class TestWritesNeverTouchBundled:
    def test_save_writes_to_the_writable_layer(self, layers):
        writable, bundled = layers
        c = Corpus(writable)
        rec = DeviceRecord(
            device=device([register("R", 0)], part_number="NEW", manufacturer="Acme Semiconductor"),
            provenance=Provenance(regforge_version="test"),
        )
        path = c.save(rec)
        assert writable in path.parents
        assert bundled not in path.parents

    def test_verifying_a_bundled_part_copies_it_out_rather_than_editing_in_place(self, layers):
        writable, bundled = layers
        bundled_path = write_record(bundled, "BME280", "Bosch Sensortec")
        before = bundled_path.read_text(encoding="utf-8")

        c = Corpus(writable)
        written = c.mark_verified("BME280", by="Reviewer")

        assert writable in written.parents, "must not write inside site-packages"
        assert bundled_path.read_text(encoding="utf-8") == before, "bundled copy must be untouched"
        assert c.get("BME280").provenance.verified is True

    def test_verifying_a_missing_part_returns_none(self, layers):
        writable, _ = layers
        assert Corpus(writable).mark_verified("NOPE", by="Reviewer") is None


class TestRobustness:
    def test_corrupt_bundled_file_does_not_break_listing(self, layers):
        writable, bundled = layers
        write_record(bundled, "BME280", "Bosch Sensortec")
        (bundled / "bosch-sensortec" / "junk.json").write_text("{not json", encoding="utf-8")
        assert len(Corpus(writable).list_all()) == 1

    def test_absent_bundled_dir_is_fine(self, tmp_path, monkeypatch):
        monkeypatch.setattr("regforge.corpus.bundled_corpus_dir", lambda: tmp_path / "does-not-exist")
        c = Corpus(tmp_path / "w")
        assert c.list_all() == []
        assert c.get("ANY") is None

    def test_search_roots_does_not_duplicate_when_layers_coincide(self, tmp_path, monkeypatch):
        # An editable install can point the bundled dir at the repo's own corpus.
        monkeypatch.setattr("regforge.corpus.bundled_corpus_dir", lambda: tmp_path)
        c = Corpus(tmp_path)
        assert len(c.search_roots) == 1


class TestShippedCorpus:
    """Guards the packaging contract itself."""

    def test_repo_corpus_holds_the_seed_part(self):
        from pathlib import Path

        repo_corpus = Path(__file__).resolve().parent.parent / "corpus"
        seeded = list(repo_corpus.glob("*/*.json"))
        assert seeded, "the repo corpus is empty; nothing would be bundled into the wheel"

        for path in seeded:
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert "device" in payload and "provenance" in payload, f"{path} is not a DeviceRecord"

    def test_every_shipped_part_validates(self):
        from pathlib import Path

        from regforge.validate import is_clean, validate_device

        repo_corpus = Path(__file__).resolve().parent.parent / "corpus"
        c = Corpus(repo_corpus, include_bundled=False)
        entries = c.list_all()
        assert entries, "no parts to check"

        for entry in entries:
            rec = c.load_path(entry.path)
            findings = validate_device(rec.device)
            assert is_clean(findings), (
                f"{entry.part_number} ships with validation errors: "
                f"{[str(f) for f in findings if f.severity.value == 'error']}"
            )

    def test_bundled_dir_helper_points_inside_the_package(self):
        assert bundled_corpus_dir().name == "corpus_data"
        assert bundled_corpus_dir().parent.name == "regforge"
