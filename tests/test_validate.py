"""The validator is the trust boundary, so these tests are the important ones.

Each case is a mistake a model actually makes when reading a register table.
"""

from __future__ import annotations

from conftest import device, field, register

from regforge.models import Access, EnumValue
from regforge.validate import (
    Severity,
    coverage_score,
    is_clean,
    summarise,
    validate_device,
)


def codes(findings, severity=None):
    return {f.code for f in findings if severity is None or f.severity is severity}


class TestCleanMap:
    def test_good_device_has_no_errors(self, good_device):
        findings = validate_device(good_device)
        assert is_clean(findings)
        assert summarise(findings)["errors"] == 0

    def test_notes_are_not_failures(self, good_device):
        # CHIP_ID has no bitfields, which is a note, not a problem.
        findings = validate_device(good_device)
        assert "NO_FIELDS" in codes(findings, Severity.INFO)
        assert is_clean(findings)


class TestBitGeometry:
    def test_overlapping_fields_are_an_error(self):
        d = device([register("CTRL", 0x00, [field("A", 0, 4), field("B", 2, 4)])])
        findings = validate_device(d)
        assert "FIELD_OVERLAP" in codes(findings, Severity.ERROR)
        assert not is_clean(findings)

    def test_adjacent_fields_do_not_overlap(self):
        d = device([register("CTRL", 0x00, [field("A", 0, 4), field("B", 4, 4)])])
        assert is_clean(validate_device(d))

    def test_field_past_end_of_register_is_an_error(self):
        # The classic [7:5] mistake: offset 7, width 3 runs off an 8-bit register.
        d = device([register("CTRL", 0x00, [field("OSRS_T", 7, 3)])])
        findings = validate_device(d)
        assert "FIELD_OVERRUNS_REGISTER" in codes(findings, Severity.ERROR)

    def test_field_exactly_filling_register_is_fine(self):
        d = device([register("DATA", 0x00, [field("VALUE", 0, 8)])])
        assert is_clean(validate_device(d))

    def test_zero_width_field_is_an_error(self):
        d = device([register("CTRL", 0x00, [field("A", 0, 0)])])
        assert "BAD_FIELD_WIDTH" in codes(validate_device(d), Severity.ERROR)

    def test_negative_offset_is_an_error(self):
        d = device([register("CTRL", 0x00, [field("A", -1, 2)])])
        assert "BAD_FIELD_OFFSET" in codes(validate_device(d), Severity.ERROR)


class TestValueFit:
    def test_register_reset_too_wide(self):
        d = device([register("CTRL", 0x00, reset_value=0x1FF, size_bits=8)])
        assert "RESET_TOO_WIDE" in codes(validate_device(d), Severity.ERROR)

    def test_field_reset_too_wide(self):
        d = device([register("CTRL", 0x00, [field("MODE", 0, 2, reset_value=7)])])
        assert "FIELD_RESET_TOO_WIDE" in codes(validate_device(d), Severity.ERROR)

    def test_enum_value_too_wide(self):
        d = device(
            [
                register(
                    "CTRL",
                    0x00,
                    [field("MODE", 0, 2, enum_values=[EnumValue(name="BIG", value=9, description=None)])],
                )
            ]
        )
        assert "ENUM_TOO_WIDE" in codes(validate_device(d), Severity.ERROR)

    def test_address_beyond_address_width(self):
        d = device([register("FAR", 0x1FF)], register_address_bits=8)
        assert "ADDRESS_OUT_OF_RANGE" in codes(validate_device(d), Severity.ERROR)

    def test_reset_mismatch_is_only_a_warning(self):
        # Register says 0x00 but the field says 1. Suspicious, not fatal --
        # datasheets do sometimes disagree with themselves.
        d = device([register("CTRL", 0x00, [field("EN", 0, 1, reset_value=1)], reset_value=0x00)])
        findings = validate_device(d)
        assert "RESET_MISMATCH" in codes(findings, Severity.WARNING)
        assert is_clean(findings)


class TestDuplicates:
    def test_duplicate_register_name(self):
        d = device([register("CTRL", 0x00), register("CTRL", 0x01)])
        assert "DUPLICATE_REGISTER" in codes(validate_device(d), Severity.ERROR)

    def test_duplicate_field_name(self):
        d = device([register("CTRL", 0x00, [field("A", 0, 1), field("A", 1, 1)])])
        assert "DUPLICATE_FIELD" in codes(validate_device(d), Severity.ERROR)

    def test_shared_address_is_a_warning_not_an_error(self):
        # Banked and read/write-split maps legitimately reuse an address.
        d = device([register("TX_DATA", 0x05), register("RX_DATA", 0x05)])
        findings = validate_device(d)
        assert "DUPLICATE_ADDRESS" in codes(findings, Severity.WARNING)
        assert is_clean(findings)


class TestIdentifiers:
    def test_leading_digit_is_only_a_note(self):
        # "0_5_MS" is a real datasheet enum name; codegen handles it losslessly.
        d = device(
            [
                register(
                    "CONFIG",
                    0x00,
                    [field("T_SB", 0, 3, enum_values=[EnumValue(name="0_5_MS", value=0, description=None)])],
                )
            ]
        )
        findings = validate_device(d)
        assert "LEADING_DIGIT" in codes(findings, Severity.INFO)
        assert "NON_C_IDENTIFIER" not in codes(findings)
        assert is_clean(findings)

    def test_genuinely_bad_name_is_a_warning(self):
        d = device([register("CTRL REG!", 0x00)])
        assert "NON_C_IDENTIFIER" in codes(validate_device(d), Severity.WARNING)

    def test_c_keyword_collision_is_a_warning(self):
        d = device([register("CTRL", 0x00, [field("int", 0, 1)])])
        assert "C_RESERVED_WORD" in codes(validate_device(d), Severity.WARNING)


class TestDeviceLevel:
    def test_no_registers_is_an_error(self):
        assert "NO_REGISTERS" in codes(validate_device(device([])), Severity.ERROR)

    def test_eight_bit_i2c_address_is_flagged(self):
        # 0xEC is 0x76 shifted left -- a very common extraction slip.
        d = device([register("CTRL", 0x00)], i2c_addresses=[0xEC])
        assert "BAD_I2C_ADDRESS" in codes(validate_device(d), Severity.WARNING)

    def test_errors_sort_before_warnings(self):
        d = device([register("CTRL", 0x00, [field("A", 0, 4), field("B", 2, 4)])], i2c_addresses=[0xEC])
        findings = validate_device(d)
        severities = [f.severity for f in findings]
        assert severities == sorted(severities, key=lambda s: {"error": 0, "warning": 1, "info": 2}[s.value])


class TestCoverage:
    def test_fully_documented_register_scores_one(self):
        d = device([register("CTRL", 0x00, [field("ALL", 0, 8)])])
        assert coverage_score(d) == 1.0

    def test_fieldless_registers_are_excluded(self):
        # Eight opaque data registers must not drag a complete map's score down.
        regs = [register("CTRL", 0x00, [field("ALL", 0, 8)])]
        regs += [register(f"DATA{i}", 0x10 + i, access=Access.RO) for i in range(8)]
        assert coverage_score(device(regs)) == 1.0

    def test_partial_coverage(self):
        d = device([register("CTRL", 0x00, [field("HALF", 0, 4)])])
        assert coverage_score(d) == 0.5

    def test_no_fields_anywhere_scores_zero(self):
        assert coverage_score(device([register("DATA", 0x00)])) == 0.0
