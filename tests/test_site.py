"""Tests for the generated site.

The site is now real logic, not just formatting: it decides which parts can
never share an I2C bus and which registers differ between similar chips. Those
claims are published on a public page that engineers might act on, so they get
the same treatment as the rest of the codebase.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from conftest import device, field, register

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from site_pages import (  # noqa: E402
    build_address_index,
    build_search_index,
    pick_related,
    render_compare,
    render_i2c,
    render_index,
    render_part,
)
from site_theme import bit_diagram, page  # noqa: E402

from regforge.models import DeviceRecord, Provenance  # noqa: E402


def rec_of(dev, **prov) -> DeviceRecord:
    return DeviceRecord(device=dev, provenance=Provenance(regforge_version="test", **prov))


def part(pn, addrs, regs=None, mf="Acme Semiconductor"):
    return rec_of(device(regs or [register("CTRL", 0x00)], part_number=pn,
                         manufacturer=mf, i2c_addresses=addrs))


# ---------------------------------------------------------------------------
# I2C conflict logic -- the claim most likely to mislead someone
# ---------------------------------------------------------------------------

class TestAddressConflicts:
    def test_address_index_groups_parts(self):
        idx = build_address_index([part("A", [0x68]), part("B", [0x68]), part("C", [0x40])])
        assert idx[0x68] == ["A", "B"]
        assert idx[0x40] == ["C"]

    def test_two_fixed_address_parts_are_unavoidable(self):
        # The DS1307 + DS3231 case: both fixed at 0x68, neither can move.
        html = render_i2c([part("A", [0x68]), part("B", [0x68])])
        assert "Cannot share a bus, ever" in html

    def test_parts_with_alternates_are_only_resolvable(self):
        # Both can strap elsewhere, so this must not be called unavoidable.
        html = render_i2c([part("A", [0x68, 0x69]), part("B", [0x68, 0x69])])
        assert "Cannot share a bus, ever" not in html
        assert "fixable by re-strapping" in html

    def test_one_fixed_one_strappable_is_resolvable(self):
        html = render_i2c([part("A", [0x68]), part("B", [0x68, 0x69])])
        assert "Cannot share a bus, ever" not in html

    def test_non_overlapping_parts_raise_nothing(self):
        html = render_i2c([part("A", [0x40]), part("B", [0x68])])
        assert "Cannot share a bus, ever" not in html
        assert "fixable by re-strapping" not in html

    def test_wide_address_range_does_not_create_false_alarms(self):
        # A part with 64 strappable addresses overlaps everything in its range.
        # That is true and useless; it must never be reported as unavoidable.
        wide = part("WIDE", list(range(0x40, 0x80)))
        html = render_i2c([wide, part("NARROW", [0x48, 0x49])])
        assert "Cannot share a bus, ever" not in html

    def test_reserved_addresses_are_excluded_from_the_grid(self):
        html = render_i2c([part("A", [0x68])])
        assert 'id="x07"' not in html, "0x00-0x07 are reserved by the I2C spec"
        assert 'id="x78"' not in html, "0x78-0x7F are reserved by the I2C spec"
        assert 'id="x08"' in html
        assert 'id="x77"' in html

    def test_conflict_warning_appears_on_the_part_page(self):
        recs = [part("A", [0x68]), part("B", [0x68])]
        html = render_part(recs[0], [], build_address_index(recs))
        assert "I²C address conflict" in html
        assert "b.html" in html

    def test_no_warning_when_a_part_is_alone_on_its_address(self):
        recs = [part("A", [0x68]), part("B", [0x40])]
        html = render_part(recs[0], [], build_address_index(recs))
        assert "I²C address conflict" not in html


# ---------------------------------------------------------------------------
# bit diagrams
# ---------------------------------------------------------------------------

class TestBitDiagram:
    def test_fields_span_their_width(self):
        r = register("CTRL", 0x00, [field("OSRS_T", 5, 3), field("MODE", 0, 2)])
        html = bit_diagram(r)
        assert "grid-column:span 3" in html
        assert "grid-column:span 2" in html

    def test_unnamed_bits_are_shown_as_single_cells(self):
        r = register("CTRL", 0x00, [field("EN", 7, 1)])
        html = bit_diagram(r)
        assert html.count("unnamed") == 7, "bits 6..0 have no field"

    def test_msb_appears_before_lsb_in_document_order(self):
        r = register("CTRL", 0x00, [field("HIGH", 6, 2), field("LOW", 0, 2)])
        html = bit_diagram(r)
        assert html.index("HIGH") < html.index("LOW"), "datasheets draw MSB on the left"

    def test_full_width_field_produces_one_cell(self):
        r = register("DATA", 0x00, [field("VALUE", 0, 8)])
        assert bit_diagram(r).count("grid-column:span 8") == 1

    def test_column_count_matches_register_width(self):
        r = register("CFG", 0x00, [field("A", 0, 4)], size_bits=16)
        assert "repeat(16,1fr)" in bit_diagram(r)

    def test_out_of_range_field_is_ignored(self):
        r = register("CTRL", 0x00, [field("BAD", 7, 3)])
        html = bit_diagram(r)
        assert "BAD" not in html

    def test_oversized_register_is_skipped(self):
        r = register("HUGE", 0x00, [field("A", 0, 1)], size_bits=64)
        assert bit_diagram(r) == ""


# ---------------------------------------------------------------------------
# comparisons
# ---------------------------------------------------------------------------

class TestCompare:
    def test_same_name_different_address_is_flagged(self):
        a = part("A", [0x68], [register("CONTROL", 0x07, reset_value=0x03)])
        b = part("B", [0x68], [register("CONTROL", 0x0E, reset_value=0x1C)])
        html = render_compare(a, b)
        assert "Same name, different behaviour" in html
        assert "CONTROL" in html

    def test_identical_registers_are_not_flagged(self):
        a = part("A", [0x40], [register("CTRL", 0x07, reset_value=0x03)])
        b = part("B", [0x41], [register("CTRL", 0x07, reset_value=0x03)])
        assert "Same name, different behaviour" not in render_compare(a, b)

    def test_unique_registers_are_listed_per_part(self):
        a = part("A", [0x40], [register("ONLY_A", 0x01)])
        b = part("B", [0x41], [register("ONLY_B", 0x02)])
        html = render_compare(a, b)
        assert "Only on the A" in html and "ONLY_A" in html
        assert "Only on the B" in html and "ONLY_B" in html

    def test_shared_address_produces_a_bus_warning(self):
        html = render_compare(part("A", [0x68]), part("B", [0x68]))
        assert "cannot share an I²C bus" in html

    def test_distinct_addresses_produce_no_warning(self):
        html = render_compare(part("A", [0x68]), part("B", [0x40]))
        assert "cannot share an I²C bus" not in html


# ---------------------------------------------------------------------------
# search index
# ---------------------------------------------------------------------------

class TestSearchIndex:
    def test_indexes_parts_registers_and_fields(self):
        p = part("ACME", [0x40], [register("CTRL", 0xF4, [field("MODE", 0, 2)])])
        kinds = {i["k"] for i in build_search_index([p])}
        assert kinds == {"part", "register", "field"}

    def test_register_entries_carry_a_searchable_address(self):
        p = part("ACME", [0x40], [register("CTRL", 0xF4)])
        reg = next(i for i in build_search_index([p]) if i["k"] == "register")
        assert reg["a"] == "0xF4"

    def test_every_entry_has_a_working_relative_url(self):
        p = part("ACME", [0x40], [register("CTRL", 0xF4, [field("MODE", 0, 2)])])
        for i in build_search_index([p]):
            assert i["u"] == "parts/acme.html"

    def test_index_is_json_serialisable(self):
        p = part("ACME", [0x40], [register("CTRL", 0xF4, [field("MODE", 0, 2)])])
        assert json.loads(json.dumps(build_search_index([p])))


# ---------------------------------------------------------------------------
# page shell
# ---------------------------------------------------------------------------

class TestPageShell:
    def test_canonical_is_absolute(self):
        html = page("T", "D", "<p>x</p>", canonical="parts/x.html", depth=1)
        assert 'rel="canonical" href="https://mathewsv-manoj.github.io/regforge/parts/x.html"' in html

    def test_nested_pages_link_up_correctly(self):
        html = page("T", "D", "<p>x</p>", canonical="parts/x.html", depth=1)
        assert 'href="../index.html"' in html

    def test_root_pages_link_flat(self):
        html = page("T", "D", "<p>x</p>", canonical="index.html", depth=0)
        assert 'href="index.html"' in html
        assert 'href="../index.html"' not in html

    def test_active_nav_item_is_marked(self):
        html = page("T", "D", "<p>x</p>", canonical="search.html", active="search.html")
        assert 'class="on"' in html

    def test_no_backslash_in_fstring_regression(self):
        # This module must import and run on Python 3.10, where a backslash
        # inside an f-string expression is a SyntaxError.
        assert sys.version_info >= (3, 10)
        assert page("T", "D", "", canonical="index.html")


class TestIndexPage:
    def test_lists_every_part(self):
        recs = [part("AAA", [0x10]), part("BBB", [0x20])]
        html = render_index(recs, 0)
        assert "AAA" in html and "BBB" in html

    def test_surfaces_the_tools(self):
        html = render_index([part("AAA", [0x10])], 3)
        assert "i2c-addresses.html" in html
        assert "search.html" in html
        assert "compare/index.html" in html

    def test_related_excludes_self_and_prefers_same_manufacturer(self):
        a = part("A", [0x10], mf="Bosch Sensortec")
        b = part("B", [0x11], mf="Bosch Sensortec")
        c = part("C", [0x12], mf="Texas Instruments")
        rel = pick_related(a, [a, b, c])
        assert [r.device.part_number for r in rel][0] == "B"
        assert "A" not in [r.device.part_number for r in rel]


@pytest.mark.parametrize("bad", [[], None])
def test_render_i2c_handles_parts_without_addresses(bad):
    p = rec_of(device([register("CTRL", 0x00)], part_number="SPIONLY", i2c_addresses=[]))
    html = render_i2c([p])
    assert "I²C address map" in html
