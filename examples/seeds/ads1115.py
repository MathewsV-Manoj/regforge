"""TI ADS1115 -- 16-bit delta-sigma ADC with PGA, comparator and I2C.

Worth having in the corpus early: it is a 16-bit register device, so it
exercises a different generator path from the 8-bit sensors, and its CONFIG
reset value of 0x8583 is fully decomposable into documented fields, which makes
it a genuine end-to-end check of the reset cross-validation.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, make_record, reg

MUX = [
    EnumValue(name="AIN0_AIN1", value=0b000, description="Differential AIN0 - AIN1 (default)"),
    EnumValue(name="AIN0_AIN3", value=0b001, description="Differential AIN0 - AIN3"),
    EnumValue(name="AIN1_AIN3", value=0b010, description="Differential AIN1 - AIN3"),
    EnumValue(name="AIN2_AIN3", value=0b011, description="Differential AIN2 - AIN3"),
    EnumValue(name="AIN0_GND", value=0b100, description="Single-ended AIN0"),
    EnumValue(name="AIN1_GND", value=0b101, description="Single-ended AIN1"),
    EnumValue(name="AIN2_GND", value=0b110, description="Single-ended AIN2"),
    EnumValue(name="AIN3_GND", value=0b111, description="Single-ended AIN3"),
]

PGA = [
    EnumValue(name="FSR_6_144V", value=0b000, description="Full-scale range +/-6.144 V"),
    EnumValue(name="FSR_4_096V", value=0b001, description="Full-scale range +/-4.096 V"),
    EnumValue(name="FSR_2_048V", value=0b010, description="Full-scale range +/-2.048 V (default)"),
    EnumValue(name="FSR_1_024V", value=0b011, description="Full-scale range +/-1.024 V"),
    EnumValue(name="FSR_0_512V", value=0b100, description="Full-scale range +/-0.512 V"),
    EnumValue(name="FSR_0_256V", value=0b101, description="Full-scale range +/-0.256 V"),
]

DATA_RATE = [
    EnumValue(name="SPS_8", value=0b000, description="8 samples per second"),
    EnumValue(name="SPS_16", value=0b001, description="16 samples per second"),
    EnumValue(name="SPS_32", value=0b010, description="32 samples per second"),
    EnumValue(name="SPS_64", value=0b011, description="64 samples per second"),
    EnumValue(name="SPS_128", value=0b100, description="128 samples per second (default)"),
    EnumValue(name="SPS_250", value=0b101, description="250 samples per second"),
    EnumValue(name="SPS_475", value=0b110, description="475 samples per second"),
    EnumValue(name="SPS_860", value=0b111, description="860 samples per second"),
]

COMP_QUE = [
    EnumValue(name="ASSERT_AFTER_1", value=0b00, description="Assert after one conversion"),
    EnumValue(name="ASSERT_AFTER_2", value=0b01, description="Assert after two conversions"),
    EnumValue(name="ASSERT_AFTER_4", value=0b10, description="Assert after four conversions"),
    EnumValue(name="DISABLED", value=0b11, description="Comparator disabled, ALERT/RDY high-Z (default)"),
]


def build_record():
    registers = [
        reg(
            "CONVERSION",
            0x00,
            size=16,
            access=Access.RO,
            reset=0x0000,
            desc="Last conversion result, two's complement, left-aligned",
        ),
        reg(
            "CONFIG",
            0x01,
            size=16,
            access=Access.RW,
            reset=0x8583,
            desc="Operating mode, input multiplexer, PGA, data rate and comparator",
            fields=[
                bits(
                    "OS",
                    15,
                    reset=1,
                    desc="Write 1 to start a single conversion; reads 0 while a conversion is running",
                    enums=[
                        EnumValue(name="BUSY", value=0, description="Conversion in progress (on read)"),
                        EnumValue(name="START", value=1, description="Start a single conversion (on write)"),
                    ],
                ),
                bits("MUX", 12, 3, reset=0b000, desc="Input multiplexer configuration", enums=MUX),
                bits("PGA", 9, 3, reset=0b010, desc="Programmable gain amplifier setting", enums=PGA),
                bits(
                    "MODE",
                    8,
                    reset=1,
                    desc="Conversion mode",
                    enums=[
                        EnumValue(name="CONTINUOUS", value=0, description="Continuous conversion"),
                        EnumValue(name="SINGLE_SHOT", value=1, description="Single-shot, power down between (default)"),
                    ],
                ),
                bits("DR", 5, 3, reset=0b100, desc="Data rate", enums=DATA_RATE),
                bits(
                    "COMP_MODE",
                    4,
                    reset=0,
                    desc="Comparator mode",
                    enums=[
                        EnumValue(name="TRADITIONAL", value=0, description="Traditional comparator (default)"),
                        EnumValue(name="WINDOW", value=1, description="Window comparator"),
                    ],
                ),
                bits(
                    "COMP_POL",
                    3,
                    reset=0,
                    desc="ALERT/RDY polarity",
                    enums=[
                        EnumValue(name="ACTIVE_LOW", value=0, description="Active low (default)"),
                        EnumValue(name="ACTIVE_HIGH", value=1, description="Active high"),
                    ],
                ),
                bits(
                    "COMP_LAT",
                    2,
                    reset=0,
                    desc="Latching comparator",
                    enums=[
                        EnumValue(name="NON_LATCHING", value=0, description="Non-latching (default)"),
                        EnumValue(name="LATCHING", value=1, description="Latching until read"),
                    ],
                ),
                bits("COMP_QUE", 0, 2, reset=0b11, desc="Comparator queue and disable", enums=COMP_QUE),
            ],
        ),
        reg(
            "LO_THRESH",
            0x02,
            size=16,
            access=Access.RW,
            reset=0x8000,
            desc="Comparator low threshold, two's complement",
        ),
        reg(
            "HI_THRESH",
            0x03,
            size=16,
            access=Access.RW,
            reset=0x7FFF,
            desc="Comparator high threshold, two's complement",
        ),
    ]

    return make_record(
        part_number="ADS1115",
        manufacturer="Texas Instruments",
        description="16-bit delta-sigma ADC with PGA, comparator and I2C interface",
        buses=[Bus.I2C],
        # ADDR pin tied to GND, VDD, SDA or SCL.
        i2c_addresses=[0x48, 0x49, 0x4A, 0x4B],
        registers=registers,
        source="TI ADS1115 datasheet (SBAS444)",
    )
