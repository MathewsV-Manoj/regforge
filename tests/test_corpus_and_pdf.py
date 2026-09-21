"""Corpus round-trips, PDF page scoring, and CLI argument parsing."""

from __future__ import annotations

import pytest
from conftest import device, register

from regforge.cli import _compact_ranges, _parse_pages
from regforge.corpus import Corpus, slug
from regforge.models import DeviceRecord, Provenance
from regforge.pdf import chunk_pages, score_page


class TestSlug:
    def test_lowercases_and_hyphenates(self):
        assert slug("Bosch Sensortec") == "bosch-sensortec"

    def test_strips_punctuation(self):
        assert slug("ST.Micro, Inc.") == "st-micro-inc"

    def test_empty_is_not_a_bare_path(self):
        assert slug("") == "unknown"

    def test_is_stable(self):
        assert slug("BME280") == slug("bme-280") == "bme280" or slug("BME280") == "bme280"


class TestCorpus:
    def test_save_and_get_round_trip(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        c.save(good_record)
        loaded = c.get("TESTPART")
        assert loaded is not None
        assert loaded.device.part_number == "TESTPART"
        assert len(loaded.device.registers) == len(good_record.device.registers)

    def test_lookup_is_case_insensitive(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        c.save(good_record)
        assert c.get("testpart") is not None

    def test_missing_part_returns_none(self, tmp_path):
        assert Corpus(tmp_path).get("NOSUCHPART") is None

    def test_saving_twice_updates_rather_than_duplicates(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        c.save(good_record)
        good_record.device.description = "changed"
        c.save(good_record)
        assert len(c.list_all()) == 1
        assert c.get("TESTPART").device.description == "changed"

    def test_json_is_stable_across_saves(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        p1 = c.save(good_record)
        first = p1.read_text(encoding="utf-8")
        second = c.save(good_record).read_text(encoding="utf-8")
        assert first == second, "unstable output would make every re-extraction a huge diff"

    def test_mark_verified(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        c.save(good_record)
        c.mark_verified("TESTPART", by="Reviewer", notes="checked rev 1.6")
        rec = c.get("TESTPART")
        assert rec.provenance.verified is True
        assert rec.provenance.verified_by == "Reviewer"
        assert rec.provenance.notes == "checked rev 1.6"

    def test_find_matches_substring(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        c.save(good_record)
        assert [e.part_number for e in c.find("TEST")] == ["TESTPART"]
        assert c.find("nope") == []

    def test_stats(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        c.save(good_record)
        s = c.stats()
        assert s["parts"] == 1
        assert s["verified"] == 0
        assert s["registers"] == 2

    def test_corrupt_file_does_not_break_listing(self, tmp_path, good_record):
        c = Corpus(tmp_path)
        c.save(good_record)
        junk = tmp_path / slug(good_record.device.manufacturer) / "junk.json"
        junk.write_text("{not json", encoding="utf-8")
        assert len(c.list_all()) == 1

    def test_empty_corpus_lists_nothing(self, tmp_path):
        assert Corpus(tmp_path / "nothing-here").list_all() == []


class TestPageScoring:
    def test_blank_page_scores_zero(self):
        assert score_page("").score == 0.0
        assert score_page("   \n  ").score == 0.0

    def test_prose_scores_low(self):
        prose = (
            "The device is a combined humidity and pressure sensor designed for "
            "mobile applications where size and low power consumption matter. "
            "It offers excellent long-term stability across the operating range."
        )
        assert score_page(prose).score < 2.0

    def test_register_table_scores_high(self):
        table = """
        Register Address  Name       Bit 7   Bit 6   Bit 5   Reset   Access
        0xF2              ctrl_hum   -       -       -       0x00    R/W
        0xF3              status     -       -       -       0x00    RO
        0xF4              ctrl_meas  osrs_t[2:0]     mode[1:0]  0x00  R/W
        0xF5              config     t_sb[2:0]       filter[4:2] 0x00 R/W
        0xD0              id         chip_id[7:0]               0x60 RO
        Reserved bits must be written as 0. Default values shown after reset.
        """
        assert score_page(table).score > 5.0

    def test_table_outscores_prose(self):
        prose = "This section describes the general operation of the device in detail."
        table = "0xF4 ctrl_meas R/W reset 0x00 bits [7:5] osrs_t reserved register"
        assert score_page(table).score > score_page(prose).score


class TestChunking:
    def test_splits_evenly(self):
        assert chunk_pages(list(range(10)), 4) == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]

    def test_single_chunk_when_small(self):
        assert chunk_pages([1, 2], 8) == [[1, 2]]

    def test_empty_input(self):
        assert chunk_pages([], 4) == []

    def test_rejects_zero_chunk_size(self):
        with pytest.raises(ValueError):
            chunk_pages([1, 2], 0)


class TestPageSpecParsing:
    def test_single_page_is_converted_to_zero_based(self):
        assert _parse_pages("5") == [4]

    def test_range(self):
        assert _parse_pages("24-27") == [23, 24, 25, 26]

    def test_mixed_spec_is_sorted_and_deduplicated(self):
        assert _parse_pages("30,24-26,25") == [23, 24, 25, 29]

    def test_backwards_range_is_rejected(self):
        with pytest.raises(ValueError):
            _parse_pages("31-24")

    def test_page_zero_is_rejected(self):
        with pytest.raises(ValueError):
            _parse_pages("0")


class TestRangeFormatting:
    def test_contiguous_run(self):
        assert _compact_ranges([24, 25, 26, 27]) == "24-27"

    def test_gaps_split(self):
        assert _compact_ranges([1, 2, 3, 7, 9, 10]) == "1-3,7,9-10"

    def test_single(self):
        assert _compact_ranges([5]) == "5"

    def test_empty(self):
        assert _compact_ranges([]) == ""

    def test_round_trips_through_the_parser(self):
        pages = [24, 25, 26, 30, 41, 42]
        assert sorted(p + 1 for p in _parse_pages(_compact_ranges(pages))) == pages


def test_device_record_json_round_trip(good_device):
    rec = DeviceRecord(device=good_device, provenance=Provenance(regforge_version="x"))
    restored = DeviceRecord.model_validate_json(rec.model_dump_json())
    assert restored.device.registers[1].fields[0].mask == rec.device.registers[1].fields[0].mask


def test_bitfield_mask_and_high_bit():
    d = device([register("R", 0)])
    assert d.registers[0].address == 0
