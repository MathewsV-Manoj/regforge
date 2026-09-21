"""TI INA219 -- high-side current/power monitor with I2C.

Another 16-bit part, and a good example of a documented reset value (0x399F)
that decomposes exactly into its fields.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, make_record, reg

ADC_SETTING = [
    EnumValue(name="RES_9BIT", value=0b0000, description="9-bit, 84 us"),
    EnumValue(name="RES_10BIT", value=0b0001, description="10-bit, 148 us"),
    EnumValue(name="RES_11BIT", value=0b0010, description="11-bit, 276 us"),
    EnumValue(name="RES_12BIT", value=0b0011, description="12-bit, 532 us (default)"),
    EnumValue(name="SAMPLES_2", value=0b1001, description="12-bit, 2 samples averaged, 1.06 ms"),
    EnumValue(name="SAMPLES_4", value=0b1010, description="12-bit, 4 samples averaged, 2.13 ms"),
    EnumValue(name="SAMPLES_8", value=0b1011, description="12-bit, 8 samples averaged, 4.26 ms"),
    EnumValue(name="SAMPLES_16", value=0b1100, description="12-bit, 16 samples averaged, 8.51 ms"),
    EnumValue(name="SAMPLES_32", value=0b1101, description="12-bit, 32 samples averaged, 17.02 ms"),
    EnumValue(name="SAMPLES_64", value=0b1110, description="12-bit, 64 samples averaged, 34.05 ms"),
    EnumValue(name="SAMPLES_128", value=0b1111, description="12-bit, 128 samples averaged, 68.10 ms"),
]

MODE = [
    EnumValue(name="POWER_DOWN", value=0b000, description="Power down"),
    EnumValue(name="SHUNT_TRIGGERED", value=0b001, description="Shunt voltage, triggered"),
    EnumValue(name="BUS_TRIGGERED", value=0b010, description="Bus voltage, triggered"),
    EnumValue(name="SHUNT_BUS_TRIGGERED", value=0b011, description="Shunt and bus, triggered"),
    EnumValue(name="ADC_OFF", value=0b100, description="ADC off / disabled"),
    EnumValue(name="SHUNT_CONTINUOUS", value=0b101, description="Shunt voltage, continuous"),
    EnumValue(name="BUS_CONTINUOUS", value=0b110, description="Bus voltage, continuous"),
    EnumValue(name="SHUNT_BUS_CONTINUOUS", value=0b111, description="Shunt and bus, continuous (default)"),
]


def build_record():
    registers = [
        reg(
            "CONFIG",
            0x00,
            size=16,
            access=Access.RW,
            reset=0x399F,
            desc="Bus voltage range, PGA gain, ADC resolution/averaging and operating mode",
            fields=[
                bits(
                    "RST",
                    15,
                    access=Access.W1P,
                    reset=0,
                    desc="Write 1 to reset all registers to their default values; self-clearing",
                ),
                bits(
                    "BRNG",
                    13,
                    reset=1,
                    desc="Bus voltage range",
                    enums=[
                        EnumValue(name="FSR_16V", value=0, description="16 V full scale"),
                        EnumValue(name="FSR_32V", value=1, description="32 V full scale (default)"),
                    ],
                ),
                bits(
                    "PG",
                    11,
                    2,
                    reset=0b11,
                    desc="Shunt voltage PGA gain and range",
                    enums=[
                        EnumValue(name="GAIN_1_40MV", value=0b00, description="Gain /1, +/-40 mV"),
                        EnumValue(name="GAIN_2_80MV", value=0b01, description="Gain /2, +/-80 mV"),
                        EnumValue(name="GAIN_4_160MV", value=0b10, description="Gain /4, +/-160 mV"),
                        EnumValue(name="GAIN_8_320MV", value=0b11, description="Gain /8, +/-320 mV (default)"),
                    ],
                ),
                bits("BADC", 7, 4, reset=0b0011, desc="Bus ADC resolution and averaging", enums=ADC_SETTING),
                bits("SADC", 3, 4, reset=0b0011, desc="Shunt ADC resolution and averaging", enums=ADC_SETTING),
                bits("MODE", 0, 3, reset=0b111, desc="Operating mode", enums=MODE),
            ],
        ),
        reg(
            "SHUNT_VOLTAGE",
            0x01,
            size=16,
            access=Access.RO,
            desc="Measured shunt voltage, two's complement. LSB weight depends on the PG setting.",
        ),
        reg(
            "BUS_VOLTAGE",
            0x02,
            size=16,
            access=Access.RO,
            desc="Measured bus voltage, plus conversion-ready and overflow flags",
            fields=[
                bits("BD", 3, 13, access=Access.RO, desc="Bus voltage data, 4 mV per LSB"),
                bits(
                    "CNVR",
                    1,
                    access=Access.RO,
                    desc="Conversion ready; cleared by reading the POWER register or writing CONFIG",
                ),
                bits("OVF", 0, access=Access.RO, desc="Math overflow: the power or current calculation was out of range"),
            ],
        ),
        reg(
            "POWER",
            0x03,
            size=16,
            access=Access.RO,
            reset=0x0000,
            desc="Calculated power. Reads zero until CALIBRATION has been written.",
        ),
        reg(
            "CURRENT",
            0x04,
            size=16,
            access=Access.RO,
            reset=0x0000,
            desc="Calculated current, two's complement. Reads zero until CALIBRATION has been written.",
        ),
        reg(
            "CALIBRATION",
            0x05,
            size=16,
            access=Access.RW,
            reset=0x0000,
            desc="Current/power scaling. Bit 0 is not used; the value is effectively 15-bit.",
        ),
    ]

    return make_record(
        part_number="INA219",
        manufacturer="Texas Instruments",
        description="High-side bidirectional current and power monitor with I2C",
        buses=[Bus.I2C],
        # A0/A1 each tie to GND, VS, SDA or SCL, giving 16 addresses from 0x40.
        i2c_addresses=list(range(0x40, 0x50)),
        registers=registers,
        source="TI INA219 datasheet (SBOS448)",
    )
