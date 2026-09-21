"""Code generation tests, including the bit arithmetic the macros encode.

The macro correctness is also checked by the generated C self-check compiled by
a real toolchain, but these run everywhere and fail faster.
"""

from __future__ import annotations

import re

from conftest import device, field, register

from regforge.codegen import c_ident, hex_literal, stdint_type
from regforge.codegen.c_driver import (
    _find_id_register,
    generate_driver_header,
    generate_driver_source,
)
from regforge.codegen.c_header import generate_regs_header
from regforge.codegen.c_tests import generate_regs_test
from regforge.models import Access, DeviceRecord, EnumValue, Provenance


def record_for(dev) -> DeviceRecord:
    return DeviceRecord(device=dev, provenance=Provenance(regforge_version="test"))


class TestIdentifiers:
    def test_basic_upper(self):
        assert c_ident("ctrl_meas") == "CTRL_MEAS"

    def test_punctuation_becomes_underscore(self):
        assert c_ident("CTRL MEAS[1:0]") == "CTRL_MEAS_1_0"

    def test_leading_digit_gets_letter_prefix_not_underscore(self):
        # An underscore prefix would concatenate into a reserved "__" sequence.
        assert c_ident("0_5_MS") == "N0_5_MS"
        assert not c_ident("0_5_MS").startswith("_")

    def test_runs_of_underscores_collapse(self):
        assert "__" not in c_ident("A -- B")

    def test_empty_name_is_handled(self):
        assert c_ident("") == "UNNAMED"

    def test_lower_mode_avoids_keywords(self):
        assert c_ident("int", upper=False) == "int_"

    def test_stdint_widths(self):
        assert stdint_type(8) == "uint8_t"
        assert stdint_type(12) == "uint16_t"
        assert stdint_type(32) == "uint32_t"

    def test_hex_literal_padding(self):
        assert hex_literal(0xF4, 8) == "0xF4u"
        assert hex_literal(0x5, 8) == "0x05u"


class TestRegsHeader:
    def test_include_guard_is_balanced(self, good_record):
        out = generate_regs_header(good_record)
        assert out.count("#ifndef TESTPART_REGS_H_") == 1
        assert out.count("#define TESTPART_REGS_H_") == 1
        assert out.rstrip().endswith("#endif /* TESTPART_REGS_H_ */")

    def test_register_address_is_defined(self, good_record):
        assert re.search(r"#define TESTPART_CTRL\s+0x0*1u", generate_regs_header(good_record))

    def test_field_macros_present(self, good_record):
        out = generate_regs_header(good_record)
        for suffix in ("SHIFT", "WIDTH", "MASK", "GET(reg)", "SET(reg, val)"):
            assert f"TESTPART_CTRL_MODE_{suffix}" in out

    def test_mask_value_is_correct(self, good_record):
        out = generate_regs_header(good_record)
        # GAIN is bits [4:2] -> mask 0x1C
        assert re.search(r"#define TESTPART_CTRL_GAIN_MASK\s+0x1Cu", out)
        # ENABLE is bit 7 -> mask 0x80
        assert re.search(r"#define TESTPART_CTRL_ENABLE_MASK\s+0x80u", out)

    def test_enum_values_emitted(self, good_record):
        out = generate_regs_header(good_record)
        assert "TESTPART_CTRL_MODE_SLEEP" in out
        assert "TESTPART_CTRL_MODE_ACTIVE" in out

    def test_unverified_map_says_so(self, good_record):
        assert "NOT VERIFIED" in generate_regs_header(good_record)

    def test_verified_map_credits_the_reviewer(self, good_record):
        good_record.provenance.verified = True
        good_record.provenance.verified_by = "M. V. Manoj"
        out = generate_regs_header(good_record)
        assert "Verified:  yes, by M. V. Manoj" in out

    def test_out_of_range_field_is_skipped_not_emitted(self):
        rec = record_for(device([register("CTRL", 0x00, [field("BAD", 7, 3)])]))
        out = generate_regs_header(rec)
        assert "SKIPPED BAD" in out
        assert "TESTPART_CTRL_BAD_MASK" not in out

    def test_colliding_names_do_not_produce_duplicate_defines(self):
        # "MODE A" and "MODE-A" both sanitise to MODE_A.
        rec = record_for(device([register("CTRL", 0x00, [field("MODE A", 0, 2), field("MODE-A", 2, 2)])]))
        out = generate_regs_header(rec)
        defines = re.findall(r"^#define (\S+)", out, re.MULTILINE)
        assert len(defines) == len(set(defines)), "duplicate #define would not compile"


class TestDriver:
    def test_identity_register_is_found(self):
        for name in ("CHIP_ID", "WHO_AM_I", "DEVICE_ID", "WHOAMI"):
            rec = record_for(device([register(name, 0x00, access=Access.RO, reset_value=0x60)]))
            assert _find_id_register(rec) is not None, name

    def test_register_with_known_reset_is_preferred(self):
        rec = record_for(
            device(
                [
                    register("ID", 0x00, access=Access.RO),
                    register("CHIP_ID", 0x01, access=Access.RO, reset_value=0x60),
                ]
            )
        )
        assert _find_id_register(rec).reset_value == 0x60

    def test_probe_is_generated_when_id_exists(self, good_record):
        assert "testpart_probe" in generate_driver_header(good_record)
        assert "TESTPART_CHIP_ID_RESET" in generate_driver_source(good_record)

    def test_probe_is_omitted_without_an_id_register(self):
        rec = record_for(device([register("CTRL", 0x00)]))
        assert "testpart_probe" not in generate_driver_header(rec)

    def test_header_includes_the_regs_header(self, good_record):
        assert '#include "testpart_regs.h"' in generate_driver_header(good_record)

    def test_update_bits_skips_redundant_writes(self, good_record):
        assert "nothing to do" in generate_driver_source(good_record)


class TestSelfCheck:
    def test_assertions_are_generated_per_field(self, good_record):
        out = generate_regs_test(good_record)
        assert out.count("REGFORGE_STATIC_ASSERT") > 20
        assert "testpart_regs.h" in out

    def test_mask_shape_assertion_present(self, good_record):
        assert "testpart_ctrl_mode_mask_shape" in generate_regs_test(good_record)

    def test_assertion_tags_are_unique(self, good_record):
        out = generate_regs_test(good_record)
        tags = re.findall(r"REGFORGE_STATIC_ASSERT\(.*,\s*(\w+)\);", out)
        assert len(tags) == len(set(tags)), "duplicate typedef tags would not compile"

    def test_set_preserve_assertion_uses_correct_complement(self):
        # GAIN is bits [4:2], mask 0x1C, so SET(0xFF, 0) must equal 0xE3.
        rec = record_for(device([register("CTRL", 0x00, [field("GAIN", 2, 3)])]))
        out = generate_regs_test(rec)
        assert "TESTPART_CTRL_GAIN_SET(0xFFu, 0u) == 0xE3u" in out

    def test_out_of_range_field_generates_no_assertions(self):
        rec = record_for(device([register("CTRL", 0x00, [field("BAD", 7, 3)])]))
        assert "TESTPART_CTRL_BAD" not in generate_regs_test(rec)


class TestMacroArithmetic:
    """Evaluate the generated GET/SET arithmetic directly, in Python."""

    @staticmethod
    def _get(reg, mask, shift):
        return (reg & mask) >> shift

    @staticmethod
    def _set(reg, val, mask, shift):
        return (reg & ~mask) | ((val << shift) & mask)

    def test_round_trip_for_every_position(self):
        for shift in range(8):
            for width in range(1, 8 - shift + 1):
                mask = ((1 << width) - 1) << shift
                maxv = (1 << width) - 1
                for v in range(maxv + 1):
                    assert self._get(self._set(0, v, mask, shift), mask, shift) == v

    def test_set_preserves_neighbours(self):
        mask, shift = 0x1C, 2  # bits [4:2]
        assert self._set(0xFF, 0, mask, shift) == 0xE3

    def test_oversized_value_cannot_corrupt_neighbours(self):
        mask, shift = 0x1C, 2
        assert self._set(0x00, 0xFF, mask, shift) & ~mask == 0
