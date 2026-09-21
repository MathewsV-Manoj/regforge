"""Seed the corpus with a hand-authored BME280 register map.

Two jobs. It gives a fresh clone something real to generate code from without
needing an API key, and it is the reference for what a good corpus entry looks
like: every field named, enums populated, reset values consistent.

The map is transcribed from the BME280 datasheet register section. It ships
unverified on purpose -- check it against BST-BME280-DS002 yourself, then run
`regforge verify BME280 --by "<your name>"`. That round trip is the workflow the
whole corpus depends on.

    python examples/seed_bme280.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from regforge import __version__  # noqa: E402
from regforge.corpus import Corpus  # noqa: E402
from regforge.models import (  # noqa: E402
    Access,
    BitField,
    Bus,
    Device,
    DeviceRecord,
    EnumValue,
    Provenance,
    Register,
)

OVERSAMPLING = [
    EnumValue(name="SKIPPED", value=0b000, description="Measurement skipped, output set to 0x80000"),
    EnumValue(name="X1", value=0b001, description="Oversampling x1"),
    EnumValue(name="X2", value=0b010, description="Oversampling x2"),
    EnumValue(name="X4", value=0b011, description="Oversampling x4"),
    EnumValue(name="X8", value=0b100, description="Oversampling x8"),
    EnumValue(name="X16", value=0b101, description="Oversampling x16"),
]


def _osrs(name: str, offset: int, what: str) -> BitField:
    return BitField(
        name=name,
        bit_offset=offset,
        bit_width=3,
        access=Access.RW,
        reset_value=0,
        description=f"Oversampling setting for {what}",
        enum_values=list(OVERSAMPLING),
    )


REGISTERS = [
    Register(
        name="CHIP_ID",
        address=0xD0,
        size_bits=8,
        access=Access.RO,
        reset_value=0x60,
        description="Chip identification number. Reads 0x60 on a BME280.",
        fields=[],
    ),
    Register(
        name="RESET",
        address=0xE0,
        size_bits=8,
        access=Access.WO,
        reset_value=0x00,
        description="Write 0xB6 to trigger a soft reset. Any other value is ignored. Reads return 0x00.",
        fields=[],
    ),
    Register(
        name="CTRL_HUM",
        address=0xF2,
        size_bits=8,
        access=Access.RW,
        reset_value=0x00,
        description="Humidity acquisition options. Changes take effect only after a write to CTRL_MEAS.",
        fields=[_osrs("OSRS_H", 0, "humidity")],
    ),
    Register(
        name="STATUS",
        address=0xF3,
        size_bits=8,
        access=Access.RO,
        reset_value=0x00,
        description="Device status.",
        fields=[
            BitField(
                name="MEASURING",
                bit_offset=3,
                bit_width=1,
                access=Access.RO,
                reset_value=0,
                description="Set while a conversion is running, cleared when results are ready",
                enum_values=[],
            ),
            BitField(
                name="IM_UPDATE",
                bit_offset=0,
                bit_width=1,
                access=Access.RO,
                reset_value=0,
                description="Set while NVM data is being copied to image registers",
                enum_values=[],
            ),
        ],
    ),
    Register(
        name="CTRL_MEAS",
        address=0xF4,
        size_bits=8,
        access=Access.RW,
        reset_value=0x00,
        description="Pressure and temperature acquisition options, and the sensor mode.",
        fields=[
            _osrs("OSRS_T", 5, "temperature"),
            _osrs("OSRS_P", 2, "pressure"),
            BitField(
                name="MODE",
                bit_offset=0,
                bit_width=2,
                access=Access.RW,
                reset_value=0,
                description="Sensor operating mode",
                enum_values=[
                    EnumValue(name="SLEEP", value=0b00, description="No measurements, minimum power"),
                    EnumValue(name="FORCED", value=0b01, description="One measurement, then return to sleep"),
                    EnumValue(name="FORCED_ALT", value=0b10, description="Alternate encoding of forced mode"),
                    EnumValue(name="NORMAL", value=0b11, description="Cycles between measuring and standby"),
                ],
            ),
        ],
    ),
    Register(
        name="CONFIG",
        address=0xF5,
        size_bits=8,
        access=Access.RW,
        reset_value=0x00,
        description="Rate, filter and interface options. Writes are ignored in normal mode.",
        fields=[
            BitField(
                name="T_SB",
                bit_offset=5,
                bit_width=3,
                access=Access.RW,
                reset_value=0,
                description="Inactive duration in normal mode",
                enum_values=[
                    EnumValue(name="0_5_MS", value=0b000, description="0.5 ms"),
                    EnumValue(name="62_5_MS", value=0b001, description="62.5 ms"),
                    EnumValue(name="125_MS", value=0b010, description="125 ms"),
                    EnumValue(name="250_MS", value=0b011, description="250 ms"),
                    EnumValue(name="500_MS", value=0b100, description="500 ms"),
                    EnumValue(name="1000_MS", value=0b101, description="1000 ms"),
                    EnumValue(name="10_MS", value=0b110, description="10 ms"),
                    EnumValue(name="20_MS", value=0b111, description="20 ms"),
                ],
            ),
            BitField(
                name="FILTER",
                bit_offset=2,
                bit_width=3,
                access=Access.RW,
                reset_value=0,
                description="IIR filter time constant",
                enum_values=[
                    EnumValue(name="OFF", value=0b000, description="Filter off"),
                    EnumValue(name="COEFF_2", value=0b001, description="Coefficient 2"),
                    EnumValue(name="COEFF_4", value=0b010, description="Coefficient 4"),
                    EnumValue(name="COEFF_8", value=0b011, description="Coefficient 8"),
                    EnumValue(name="COEFF_16", value=0b100, description="Coefficient 16"),
                ],
            ),
            BitField(
                name="SPI3W_EN",
                bit_offset=0,
                bit_width=1,
                access=Access.RW,
                reset_value=0,
                description="Enable 3-wire SPI interface",
                enum_values=[],
            ),
        ],
    ),
]

# Burst-readable measurement output. Documented as plain data registers.
for _name, _addr, _reset, _desc in [
    ("PRESS_MSB", 0xF7, 0x80, "Raw pressure, bits [19:12]"),
    ("PRESS_LSB", 0xF8, 0x00, "Raw pressure, bits [11:4]"),
    ("PRESS_XLSB", 0xF9, 0x00, "Raw pressure, bits [3:0] in bits [7:4]"),
    ("TEMP_MSB", 0xFA, 0x80, "Raw temperature, bits [19:12]"),
    ("TEMP_LSB", 0xFB, 0x00, "Raw temperature, bits [11:4]"),
    ("TEMP_XLSB", 0xFC, 0x00, "Raw temperature, bits [3:0] in bits [7:4]"),
    ("HUM_MSB", 0xFD, 0x80, "Raw humidity, bits [15:8]"),
    ("HUM_LSB", 0xFE, 0x00, "Raw humidity, bits [7:0]"),
]:
    REGISTERS.append(
        Register(
            name=_name,
            address=_addr,
            size_bits=8,
            access=Access.RO,
            reset_value=_reset,
            description=_desc,
            fields=[],
        )
    )


def build_record() -> DeviceRecord:
    device = Device(
        part_number="BME280",
        manufacturer="Bosch Sensortec",
        description="Combined humidity, pressure and temperature sensor",
        buses=[Bus.I2C, Bus.SPI],
        i2c_addresses=[0x76, 0x77],
        register_address_bits=8,
        registers=sorted(REGISTERS, key=lambda r: r.address),
    )
    provenance = Provenance(
        source_filename="BST-BME280-DS002 (hand-transcribed)",
        source_pages=[],
        extraction_model=None,
        regforge_version=__version__,
        verified=False,
        notes=(
            "Hand-authored seed entry, not machine-extracted. Check against the "
            "datasheet register section before trusting it, then mark it verified."
        ),
    )
    return DeviceRecord(device=device, provenance=provenance)


if __name__ == "__main__":
    record = build_record()
    corpus = Corpus(Path(__file__).resolve().parent.parent / "corpus")
    path = corpus.save(record)
    print(f"seeded {record.device.part_number}: {len(record.device.registers)} registers -> {path}")
