"""End-to-end tests over a real PDF file.

Everything here was previously exercised only against Python strings, which
says nothing about what pypdf actually hands back after extracting a page.
"""

from __future__ import annotations

import pytest
from fake_datasheet import (
    EXPECTED_REGISTER_PAGES,
    PROSE_FRONT,
    REGISTER_PAGES,
    TOTAL_PAGES,
    build_fake_datasheet,
)
from pypdf import PdfReader

from regforge.pdf import find_register_pages, load_pdf, score_page, slice_pdf


@pytest.fixture(scope="module")
def datasheet(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("ds") / "acme1234.pdf"
    return build_fake_datasheet(path)


class TestLoad:
    def test_page_count_matches(self, datasheet):
        assert load_pdf(datasheet).page_count == TOTAL_PAGES

    def test_text_is_actually_extracted(self, datasheet):
        pdf = load_pdf(datasheet)
        assert any("CTRL_MEAS" in t for t in pdf.page_texts)
        assert any("General Description" in t for t in pdf.page_texts)

    def test_sha256_is_stable_and_content_addressed(self, datasheet, tmp_path):
        first = load_pdf(datasheet).sha256
        assert first == load_pdf(datasheet).sha256

        other = build_fake_datasheet(tmp_path / "other.pdf", registers=REGISTER_PAGES[:1])
        assert load_pdf(other).sha256 != first

    def test_filename_is_recorded(self, datasheet):
        assert load_pdf(datasheet).filename == "acme1234.pdf"


class TestDetection:
    def test_finds_the_register_section(self, datasheet):
        selected = find_register_pages(load_pdf(datasheet))
        # Every real register page must be picked up.
        for page in EXPECTED_REGISTER_PAGES:
            assert page in selected, f"missed register page {page + 1}"

    def test_does_not_select_the_whole_document(self, datasheet):
        selected = find_register_pages(load_pdf(datasheet))
        assert len(selected) < TOTAL_PAGES, "selecting everything defeats the cost saving"

    def test_prose_pages_score_below_register_pages(self, datasheet):
        pdf = load_pdf(datasheet)
        reg_scores = [score_page(pdf.page_texts[i]).score for i in EXPECTED_REGISTER_PAGES]
        prose_scores = [score_page(pdf.page_texts[i]).score for i in range(len(PROSE_FRONT))]
        assert min(reg_scores) > max(prose_scores)

    def test_max_pages_is_respected(self, datasheet):
        selected = find_register_pages(load_pdf(datasheet), max_pages=2)
        assert len(selected) <= 2

    def test_selection_is_sorted_document_order(self, datasheet):
        selected = find_register_pages(load_pdf(datasheet), max_pages=3)
        assert selected == sorted(selected), "model should read pages in datasheet order"

    def test_falls_back_rather_than_returning_nothing(self, tmp_path):
        # A document with no register tables at all must still yield something,
        # so the user gets a slice to inspect instead of a dead end.
        path = build_fake_datasheet(tmp_path / "prose.pdf", registers=[], back=[])
        assert isinstance(find_register_pages(load_pdf(path)), list)


class TestSlicing:
    def test_slice_has_the_requested_page_count(self, datasheet):
        data = slice_pdf(datasheet, [3, 4, 5])
        assert len(PdfReader(__import__("io").BytesIO(data)).pages) == 3

    def test_slice_is_a_valid_pdf(self, datasheet):
        assert slice_pdf(datasheet, [3]).startswith(b"%PDF")

    def test_slice_keeps_the_right_content(self, datasheet):
        import io

        data = slice_pdf(datasheet, EXPECTED_REGISTER_PAGES)
        text = " ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        assert "CTRL_MEAS" in text
        assert "General Description" not in text, "sliced in a prose page we are paying for"

    def test_empty_selection_is_rejected(self, datasheet):
        with pytest.raises(ValueError):
            slice_pdf(datasheet, [])

    def test_out_of_range_pages_are_skipped_not_fatal(self, datasheet):
        import io

        data = slice_pdf(datasheet, [0, 999])
        assert len(PdfReader(io.BytesIO(data)).pages) == 1

    def test_slice_is_much_smaller_than_the_original(self, datasheet):
        import os

        assert len(slice_pdf(datasheet, [3])) < os.path.getsize(datasheet)


class TestScanCommand:
    def test_scan_runs_over_a_real_pdf(self, datasheet, capsys):
        from regforge.cli import main

        assert main(["scan", datasheet]) == 0
        out = capsys.readouterr().out
        assert "acme1234.pdf" in out
        assert "selected" in out
        assert "regforge extract" in out

    def test_scan_needs_no_api_key(self, datasheet, monkeypatch, capsys):
        from regforge.cli import main

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert main(["scan", datasheet]) == 0
