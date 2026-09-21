"""Width-aware driver generation.

The bug these exist for: the driver generator emitted `uint8_t *value`
accessors for every part regardless of register width, so a 16-bit device like
the ADS1115 got a driver that reads one byte of a two-byte register. It
compiled, it looked reasonable, and it was wrong.

Two layers of checking here. The structural tests assert the generator declares
the right types and constants. `TestByteAssemblyModel` mirrors the exact shift
expressions the generated C contains and proves the round-trip property over
every value, which is the part that cannot be checked by reading the output.
The C itself is compiled and *run* in CI against a fake transport -- see
`tests/c_runtime/`.
"""

from __future__ import annotations

import re

import pytest
from conftest import device, field, register

from regforge.codegen.c_driver import (
    _uniform_width,
    generate_driver_header,
    generate_driver_source,
)
from regforge.models import Access, DeviceRecord, Provenance


def record_for(dev, **prov) -> DeviceRecord:
    return DeviceRecord(device=dev, provenance=Provenance(regforge_version="test", **prov))


def dev_8bit():
    return device(
        [
            register("CHIP_ID", 0x00, access=Access.RO, reset_value=0x5A),
            register("CTRL", 0x01, [field("MODE", 0, 2)], size_bits=8),
        ]
    )


def dev_16bit():
    return device(
        [
            register("CONVERSION", 0x00, size_bits=16, access=Access.RO, reset_value=0x0000),
            register("CONFIG", 0x01, [field("MUX", 12, 3)], size_bits=16, reset_value=0x8583),
        ]
    )


def dev_mixed():
    return device(
        [
            register("STATUS", 0x00, size_bits=8),
            register("DATA", 0x01, size_bits=16),
        ]
    )


class TestUniformWidth:
    def test_detects_eight_bit(self):
        assert _uniform_width(record_for(dev_8bit())) == 8

    def test_detects_sixteen_bit(self):
        assert _uniform_width(record_for(dev_16bit())) == 16

    def test_mixed_returns_none(self):
        assert _uniform_width(record_for(dev_mixed())) is None


class TestGeneratedTypes:
    def test_eight_bit_part_uses_uint8(self):
        h = generate_driver_header(record_for(dev_8bit()))
        assert "typedef uint8_t testpart_reg_t;" in h
        assert "#define TESTPART_REG_BYTES 1u" in h

    def test_sixteen_bit_part_uses_uint16(self):
        h = generate_driver_header(record_for(dev_16bit()))
        assert "typedef uint16_t testpart_reg_t;" in h
        assert "#define TESTPART_REG_BYTES 2u" in h

    def test_sixteen_bit_accessors_are_not_byte_sized(self):
        # The actual regression: read_reg must not take a uint8_t* on a 16-bit part.
        h = generate_driver_header(record_for(dev_16bit()))
        assert "testpart_read_reg(const testpart_t *dev, uint8_t reg, testpart_reg_t *value)" in h
        assert "uint8_t *value" not in h

    def test_byte_order_is_documented_only_when_it_matters(self):
        assert "LSB_FIRST" in generate_driver_header(record_for(dev_16bit()))
        # A one-byte register has no byte order to get wrong.
        assert "LSB_FIRST" not in generate_driver_header(record_for(dev_8bit()))

    def test_mixed_width_part_refuses_to_invent_an_accessor(self):
        h = generate_driver_header(record_for(dev_mixed()))
        assert "mixes register widths" in h
        assert "#define TESTPART_REG_BYTES 1u" in h

    def test_source_guards_both_byte_orders(self):
        src = generate_driver_source(record_for(dev_16bit()))
        assert "#ifdef TESTPART_LSB_FIRST" in src
        assert src.count("#ifdef TESTPART_LSB_FIRST") == src.count("#else")


class TestProvenanceWording:
    def test_hand_transcribed_is_not_called_machine_extracted(self):
        h = generate_driver_header(record_for(dev_8bit()))
        assert "hand-transcribed, NOT VERIFIED" in h
        assert "MACHINE-EXTRACTED" not in h

    def test_machine_extracted_says_so(self):
        h = generate_driver_header(record_for(dev_8bit(), extraction_model="claude-sonnet-5"))
        assert "MACHINE-EXTRACTED, NOT VERIFIED" in h

    def test_verified_credits_the_reviewer(self):
        h = generate_driver_header(record_for(dev_8bit(), verified=True, verified_by="M. V. Manoj"))
        assert "verified register map (checked by M. V. Manoj)" in h
        assert "NOT VERIFIED" not in h


class TestByteAssemblyModel:
    """Mirrors the shift expressions in the generated C, exactly.

    generated write:  buf[i] = value >> (8 * (REG_BYTES - 1 - i))        [MSB first]
                      buf[i] = value >> (8 * i)                          [LSB first]
    generated read:   acc  |= buf[i] << (8 * (REG_BYTES - 1 - i))        [MSB first]
                      acc  |= buf[i] << (8 * i)                          [LSB first]
    """

    @staticmethod
    def _shift(i: int, reg_bytes: int, lsb_first: bool) -> int:
        return 8 * (i if lsb_first else reg_bytes - 1 - i)

    @classmethod
    def write(cls, value: int, reg_bytes: int, lsb_first: bool) -> list[int]:
        return [(value >> cls._shift(i, reg_bytes, lsb_first)) & 0xFF for i in range(reg_bytes)]

    @classmethod
    def read(cls, buf: list[int], reg_bytes: int, lsb_first: bool) -> int:
        acc = 0
        for i in range(reg_bytes):
            acc |= buf[i] << cls._shift(i, reg_bytes, lsb_first)
        return acc

    def test_msb_first_puts_the_high_byte_on_the_wire_first(self):
        # The ADS1115 CONFIG reset value. A byte-swap bug here is silent.
        assert self.write(0x8583, 2, lsb_first=False) == [0x85, 0x83]

    def test_lsb_first_reverses_it(self):
        assert self.write(0x8583, 2, lsb_first=True) == [0x83, 0x85]

    @pytest.mark.parametrize("lsb_first", [False, True])
    @pytest.mark.parametrize("reg_bytes", [1, 2, 4])
    def test_round_trip_is_exhaustive_or_broad(self, reg_bytes, lsb_first):
        width = reg_bytes * 8
        if width <= 16:
            values = range(1 << width)
        else:
            values = [0, 1, 0xFF, 0x100, 0x12345678, 0x80000000, 0xFFFFFFFF, 0xDEADBEEF]
        for v in values:
            buf = self.write(v, reg_bytes, lsb_first)
            assert all(0 <= b <= 0xFF for b in buf)
            assert self.read(buf, reg_bytes, lsb_first) == v

    def test_single_byte_path_does_not_shift(self):
        # At REG_BYTES == 1 the loop must degenerate to a copy.
        for v in range(256):
            assert self.write(v, 1, lsb_first=False) == [v]
            assert self.write(v, 1, lsb_first=True) == [v]

    def test_the_two_orders_actually_differ(self):
        # Guards against a refactor that collapses both branches into one.
        assert self.write(0x1234, 2, lsb_first=False) != self.write(0x1234, 2, lsb_first=True)

    def test_model_matches_the_shifts_in_the_generated_source(self):
        src = generate_driver_source(record_for(dev_16bit()))
        assert "(8u * (TESTPART_REG_BYTES - 1u - i))" in src, "MSB-first shift changed"
        assert "(8u * i)" in src, "LSB-first shift changed"


class TestRuntimeHarnessesExist:
    """The C harnesses are what CI actually runs; losing them would be silent."""

    @pytest.mark.parametrize("name", ["ads1115_runtime_test.c", "bme280_runtime_test.c"])
    def test_harness_is_present_and_checks_reg_bytes(self, name):
        from pathlib import Path

        path = Path(__file__).resolve().parent / "c_runtime" / name
        assert path.is_file(), f"{name} is missing; CI would silently stop running it"
        body = path.read_text(encoding="utf-8")
        assert "REG_BYTES" in body
        assert re.search(r"return\s+1;", body), "harness must fail with a non-zero exit code"
