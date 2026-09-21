"""Bosch Sensortec BME280 -- humidity, pressure and temperature sensor.

The reference seed: every field named, enums populated, reset values that agree
with their register. If you are adding a part to the corpus, copy the shape of
this file.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, data_regs, make_record, reg

OVERSAMPLING = [
    EnumValue(name="SKIPPED", value=0b000, description="Measurement skipped, output set to 0x80000"),
    EnumValue(name="X1", value=0b001, description="Oversampling x1"),
    EnumValue(name="X2", value=0b010, description="Oversampling x2"),
    EnumValue(name="X4", value=0b011, description="Oversampling x4"),
    EnumValue(name="X8", value=0b100, description="Oversampling x8"),
    EnumValue(name="X16", value=0b101, description="Oversampling x16"),
]


def build_record():
    registers = [
        reg(
            "CHIP_ID",
            0xD0,
            access=Access.RO,
            reset=0x60,
            desc="Chip identification number. Reads 0x60 on a BME280 (0x58 on a BMP280).",
        ),
        reg(
            "RESET",
            0xE0,
            access=Access.WO,
            reset=0x00,
            desc="Write 0xB6 to trigger a soft reset. Any other value is ignored. Reads return 0x00.",
        ),
        reg(
            "CTRL_HUM",
            0xF2,
            reset=0x00,
            desc="Humidity acquisition options. Changes take effect only after a write to CTRL_MEAS.",
            fields=[
                bits("OSRS_H", 0, 3, reset=0, desc="Oversampling setting for humidity", enums=list(OVERSAMPLING)),
            ],
        ),
        reg(
            "STATUS",
            0xF3,
            access=Access.RO,
            reset=0x00,
            desc="Device status",
            fields=[
                bits("MEASURING", 3, access=Access.RO, reset=0, desc="Set while a conversion is running"),
                bits(
                    "IM_UPDATE",
                    0,
                    access=Access.RO,
                    reset=0,
                    desc="Set while NVM data is being copied to image registers",
                ),
            ],
        ),
        reg(
            "CTRL_MEAS",
            0xF4,
            reset=0x00,
            desc="Pressure and temperature acquisition options, and the sensor mode",
            fields=[
                bits("OSRS_T", 5, 3, reset=0, desc="Oversampling setting for temperature", enums=list(OVERSAMPLING)),
                bits("OSRS_P", 2, 3, reset=0, desc="Oversampling setting for pressure", enums=list(OVERSAMPLING)),
                bits(
                    "MODE",
                    0,
                    2,
                    reset=0,
                    desc="Sensor operating mode",
                    enums=[
                        EnumValue(name="SLEEP", value=0b00, description="No measurements, minimum power"),
                        EnumValue(name="FORCED", value=0b01, description="One measurement, then return to sleep"),
                        EnumValue(name="FORCED_ALT", value=0b10, description="Alternate encoding of forced mode"),
                        EnumValue(name="NORMAL", value=0b11, description="Cycles between measuring and standby"),
                    ],
                ),
            ],
        ),
        reg(
            "CONFIG",
            0xF5,
            reset=0x00,
            desc="Rate, filter and interface options. Writes are ignored in normal mode.",
            fields=[
                bits(
                    "T_SB",
                    5,
                    3,
                    reset=0,
                    desc="Inactive duration in normal mode",
                    enums=[
                        EnumValue(name="0_5_MS", value=0b000, description="0.5 ms"),
                        EnumValue(name="62_5_MS", value=0b001, description="62.5 ms"),
                        EnumValue(name="125_MS", value=0b010, description="125 ms"),
                        EnumValue(name="250_MS", value=0b011, description="250 ms"),
                        EnumValue(name="500_MS", value=0b100, description="500 ms"),
                        EnumValue(name="1000_MS", value=0b101, description="1000 ms"),
                        EnumValue(name="10_MS", value=0b110, description="10 ms -- differs from the BMP280"),
                        EnumValue(name="20_MS", value=0b111, description="20 ms -- differs from the BMP280"),
                    ],
                ),
                bits(
                    "FILTER",
                    2,
                    3,
                    reset=0,
                    desc="IIR filter time constant",
                    enums=[
                        EnumValue(name="OFF", value=0b000, description="Filter off"),
                        EnumValue(name="COEFF_2", value=0b001, description="Coefficient 2"),
                        EnumValue(name="COEFF_4", value=0b010, description="Coefficient 4"),
                        EnumValue(name="COEFF_8", value=0b011, description="Coefficient 8"),
                        EnumValue(name="COEFF_16", value=0b100, description="Coefficient 16"),
                    ],
                ),
                bits("SPI3W_EN", 0, reset=0, desc="Enable 3-wire SPI interface"),
            ],
        ),
    ]

    registers += data_regs(
        [
            ("PRESS_MSB", 0xF7, 0x80, "Raw pressure, bits [19:12]"),
            ("PRESS_LSB", 0xF8, 0x00, "Raw pressure, bits [11:4]"),
            ("PRESS_XLSB", 0xF9, 0x00, "Raw pressure, bits [3:0] in bits [7:4]"),
            ("TEMP_MSB", 0xFA, 0x80, "Raw temperature, bits [19:12]"),
            ("TEMP_LSB", 0xFB, 0x00, "Raw temperature, bits [11:4]"),
            ("TEMP_XLSB", 0xFC, 0x00, "Raw temperature, bits [3:0] in bits [7:4]"),
            ("HUM_MSB", 0xFD, 0x80, "Raw humidity, bits [15:8]"),
            ("HUM_LSB", 0xFE, 0x00, "Raw humidity, bits [7:0]"),
        ]
    )

    return make_record(
        part_number="BME280",
        manufacturer="Bosch Sensortec",
        description="Combined humidity, pressure and temperature sensor",
        buses=[Bus.I2C, Bus.SPI],
        i2c_addresses=[0x76, 0x77],
        registers=registers,
        source="BST-BME280-DS002",
    )
