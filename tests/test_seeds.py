"""Tests over the hand-authored seed corpus.

These exist because the seeds are the product for anyone who has not yet run an
extraction. A transcription slip here ships to every user and generates wrong
driver code, so the spot checks below pin the facts most likely to drift: chip
IDs, the bit positions everyone gets backwards, and the reset values that a
whole register decomposes into.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "examples"))

from seeds import SEEDS  # noqa: E402

from regforge.validate import is_clean, validate_device  # noqa: E402


@pytest.fixture(scope="module")
def built():
    return {part: build() for part, build in SEEDS.items()}


def regs_of(record):
    return {r.name: r for r in record.device.registers}


def field_of(record, reg_name, field_name):
    reg = regs_of(record)[reg_name]
    return next(f for f in reg.fields if f.name == field_name)


class TestEverySeed:
    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_validates_clean(self, part, built):
        findings = validate_device(built[part].device)
        errors = [str(f) for f in findings if f.severity.value == "error"]
        assert is_clean(findings), f"{part} has errors: {errors}"

    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_part_number_matches_its_key(self, part, built):
        assert built[part].device.part_number == part

    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_ships_unverified_with_a_note(self, part, built):
        p = built[part].provenance
        assert p.verified is False, "a hand-transcribed map must not claim to be verified"
        assert p.notes and "verif" in p.notes.lower()
        assert p.source_filename

    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_has_registers_and_a_manufacturer(self, part, built):
        d = built[part].device
        assert d.registers
        assert d.manufacturer.strip()
        assert d.description

    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_i2c_addresses_are_seven_bit(self, part, built):
        for addr in built[part].device.i2c_addresses:
            assert 0 <= addr <= 0x7F, f"{part} has an 8-bit-looking address 0x{addr:X}"

    def test_part_numbers_are_unique(self, built):
        numbers = [r.device.part_number for r in built.values()]
        assert len(numbers) == len(set(numbers))


class TestResetDecomposition:
    """The validator cross-checks a register's reset against its fields.

    These parts have fully-documented reset values, so a clean validation is
    real evidence the bit positions are right -- not just self-consistent.
    """

    def test_ads1115_config_reset(self, built):
        reg = regs_of(built["ADS1115"])["CONFIG"]
        assert reg.reset_value == 0x8583
        composed = 0
        for f in reg.fields:
            composed |= (f.reset_value & ((1 << f.bit_width) - 1)) << f.bit_offset
        assert composed == 0x8583, "field resets do not reconstruct the documented register reset"

    def test_ina219_config_reset(self, built):
        reg = regs_of(built["INA219"])["CONFIG"]
        assert reg.reset_value == 0x399F
        composed = 0
        for f in reg.fields:
            composed |= (f.reset_value & ((1 << f.bit_width) - 1)) << f.bit_offset
        assert composed == 0x399F

    def test_ds3231_control_reset(self, built):
        reg = regs_of(built["DS3231"])["CONTROL"]
        assert reg.reset_value == 0x1C
        composed = 0
        for f in reg.fields:
            composed |= (f.reset_value & ((1 << f.bit_width) - 1)) << f.bit_offset
        assert composed == 0x1C


class TestKnownFacts:
    """Spot checks on the details that cost a day when they are wrong."""

    def test_bme280_and_bmp280_chip_ids_differ(self, built):
        assert regs_of(built["BME280"])["CHIP_ID"].reset_value == 0x60
        assert regs_of(built["BMP280"])["CHIP_ID"].reset_value == 0x58

    def test_bme280_ctrl_meas_bit_positions(self, built):
        osrs_t = field_of(built["BME280"], "CTRL_MEAS", "OSRS_T")
        assert (osrs_t.bit_offset, osrs_t.bit_width, osrs_t.mask) == (5, 3, 0xE0)
        mode = field_of(built["BME280"], "CTRL_MEAS", "MODE")
        assert (mode.bit_offset, mode.bit_width, mode.mask) == (0, 2, 0x03)

    def test_bme280_and_bmp280_standby_encodings_diverge(self, built):
        # The trap when porting a driver between the two parts.
        def enum_map(part):
            return {e.name: e.value for e in field_of(built[part], "CONFIG", "T_SB").enum_values}

        assert "10_MS" in enum_map("BME280")
        assert "2000_MS" in enum_map("BMP280")
        assert enum_map("BME280")["10_MS"] == 0b110
        assert enum_map("BMP280")["2000_MS"] == 0b110

    def test_mpu6050_wakes_up_asleep(self, built):
        pwr = regs_of(built["MPU6050"])["PWR_MGMT_1"]
        assert pwr.reset_value == 0x40, "MPU6050 resets with SLEEP set; drivers must clear it"
        sleep = field_of(built["MPU6050"], "PWR_MGMT_1", "SLEEP")
        assert (sleep.bit_offset, sleep.reset_value) == (6, 1)

    def test_mpu6050_identity(self, built):
        who = regs_of(built["MPU6050"])["WHO_AM_I"]
        assert (who.address, who.reset_value) == (0x75, 0x68)

    def test_mcp23017_iodir_defaults_to_inputs(self, built):
        assert regs_of(built["MCP23017"])["IODIRA"].reset_value == 0xFF
        assert regs_of(built["MCP23017"])["IODIRB"].reset_value == 0xFF

    def test_mcp23017_iocon_is_emitted_once(self, built):
        names = [r.name for r in built["MCP23017"].device.registers]
        assert names.count("IOCON") == 1, "the 0x0B alias must be a note, not a second register"
        iocon = regs_of(built["MCP23017"])["IOCON"]
        assert iocon.address == 0x0A
        assert "0x0B" in iocon.description

    def test_ds3231_timekeeping_has_no_invented_reset(self, built):
        # The datasheet states none; a fabricated 0x00 would be a defect.
        for name in ("SECONDS", "MINUTES", "HOURS", "DATE", "YEAR"):
            assert regs_of(built["DS3231"])[name].reset_value is None

    def test_sixteen_bit_parts_declare_sixteen_bit_registers(self, built):
        for part in ("ADS1115", "INA219"):
            assert all(r.size_bits == 16 for r in built[part].device.registers), part


class TestGeneratedOutput:
    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_header_generates(self, part, built):
        from regforge.codegen.c_header import generate_regs_header

        out = generate_regs_header(built[part])
        assert f"#ifndef {part}_REGS_H_" in out
        assert out.rstrip().endswith(f"#endif /* {part}_REGS_H_ */")

    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_self_check_generates_assertions(self, part, built):
        from regforge.codegen.c_tests import generate_regs_test

        assert generate_regs_test(built[part]).count("REGFORGE_STATIC_ASSERT") > 10

    def test_sixteen_bit_register_uses_uint16(self, built):
        from regforge.codegen.c_header import generate_regs_header

        out = generate_regs_header(built["ADS1115"])
        assert "uint16_t" in out
        assert "ADS1115_CONFIG_MUX_MASK" in out
        assert "0x7000u" in out, "MUX is bits [14:12]"

    @pytest.mark.parametrize("part", sorted(SEEDS))
    def test_no_duplicate_defines(self, part, built):
        import re

        from regforge.codegen.c_header import generate_regs_header

        defines = re.findall(r"^#define (\S+)", generate_regs_header(built[part]), re.MULTILINE)
        dupes = {d for d in defines if defines.count(d) > 1}
        assert not dupes, f"{part} would not compile: duplicate {dupes}"


class TestSeedRunner:
    def test_check_mode_passes_and_writes_nothing(self, tmp_path, capsys):
        from seed_corpus import main

        assert main(["--check", "--corpus", str(tmp_path)]) == 0
        assert not list(tmp_path.glob("*/*.json"))
        assert "0 failed" in capsys.readouterr().out

    def test_writes_every_seed(self, tmp_path):
        from seed_corpus import main

        assert main(["--corpus", str(tmp_path)]) == 0
        assert len(list(tmp_path.glob("*/*.json"))) == len(SEEDS)

    def test_single_part(self, tmp_path):
        from seed_corpus import main

        assert main(["--corpus", str(tmp_path), "BME280"]) == 0
        assert len(list(tmp_path.glob("*/*.json"))) == 1

    def test_unknown_part_is_an_error(self, tmp_path, capsys):
        from seed_corpus import main

        assert main(["--corpus", str(tmp_path), "NOSUCHPART"]) == 1
