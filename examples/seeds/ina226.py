"""TI INA226 -- current/power monitor with alert, I2C.

The successor to the INA219, and seeded next to it on purpose: the register
count differs, the CONFIG layout is completely different, and drivers get
ported between them incorrectly.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, make_record, reg

CONV_TIME = [
    EnumValue(name="US_140", value=0b000, description="140 us"),
    EnumValue(name="US_204", value=0b001, description="204 us"),
    EnumValue(name="US_332", value=0b010, description="332 us"),
    EnumValue(name="US_588", value=0b011, description="588 us"),
    EnumValue(name="US_1100", value=0b100, description="1.1 ms (default)"),
    EnumValue(name="US_2116", value=0b101, description="2.116 ms"),
    EnumValue(name="US_4156", value=0b110, description="4.156 ms"),
    EnumValue(name="US_8244", value=0b111, description="8.244 ms"),
]

AVG = [
    EnumValue(name="SAMPLES_1", value=0b000, description="1 sample (default)"),
    EnumValue(name="SAMPLES_4", value=0b001, description="4 samples averaged"),
    EnumValue(name="SAMPLES_16", value=0b010, description="16 samples averaged"),
    EnumValue(name="SAMPLES_64", value=0b011, description="64 samples averaged"),
    EnumValue(name="SAMPLES_128", value=0b100, description="128 samples averaged"),
    EnumValue(name="SAMPLES_256", value=0b101, description="256 samples averaged"),
    EnumValue(name="SAMPLES_512", value=0b110, description="512 samples averaged"),
    EnumValue(name="SAMPLES_1024", value=0b111, description="1024 samples averaged"),
]

MODE = [
    EnumValue(name="POWER_DOWN", value=0b000, description="Power down"),
    EnumValue(name="SHUNT_TRIGGERED", value=0b001, description="Shunt voltage, triggered"),
    EnumValue(name="BUS_TRIGGERED", value=0b010, description="Bus voltage, triggered"),
    EnumValue(name="SHUNT_BUS_TRIGGERED", value=0b011, description="Shunt and bus, triggered"),
    EnumValue(name="POWER_DOWN_ALT", value=0b100, description="Power down (alternate encoding)"),
    EnumValue(name="SHUNT_CONTINUOUS", value=0b101, description="Shunt voltage, continuous"),
    EnumValue(name="BUS_CONTINUOUS", value=0b110, description="Bus voltage, continuous"),
    EnumValue(name="SHUNT_BUS_CONTINUOUS", value=0b111, description="Shunt and bus, continuous (default)"),
]


def build_record():
    registers = [
        reg(
            "CONFIG", 0x00, size=16, reset=0x4127,
            desc="Averaging, conversion times and operating mode",
            fields=[
                bits("RST", 15, access=Access.W1P, reset=0,
                     desc="Write 1 to reset every register to its default; self-clearing"),
                bits("AVG", 9, 3, reset=0b000, desc="Averaging mode", enums=AVG),
                bits("VBUSCT", 6, 3, reset=0b100, desc="Bus voltage conversion time", enums=CONV_TIME),
                bits("VSHCT", 3, 3, reset=0b100, desc="Shunt voltage conversion time", enums=CONV_TIME),
                bits("MODE", 0, 3, reset=0b111, desc="Operating mode", enums=MODE),
            ],
        ),
        reg("SHUNT_VOLTAGE", 0x01, size=16, access=Access.RO,
            desc="Measured shunt voltage, two's complement, 2.5 uV per LSB"),
        reg("BUS_VOLTAGE", 0x02, size=16, access=Access.RO,
            desc="Measured bus voltage, 1.25 mV per LSB"),
        reg("POWER", 0x03, size=16, access=Access.RO, reset=0x0000,
            desc="Calculated power. Reads zero until CALIBRATION has been written."),
        reg("CURRENT", 0x04, size=16, access=Access.RO, reset=0x0000,
            desc="Calculated current, two's complement. Reads zero until CALIBRATION has been written."),
        reg("CALIBRATION", 0x05, size=16, reset=0x0000,
            desc="Current and power scaling. Set from the shunt resistance and the maximum expected current."),
        reg(
            "MASK_ENABLE", 0x06, size=16, reset=0x0000,
            desc="Alert source selection and status flags",
            fields=[
                bits("SOL", 15, reset=0, desc="Alert on shunt voltage over limit"),
                bits("SUL", 14, reset=0, desc="Alert on shunt voltage under limit"),
                bits("BOL", 13, reset=0, desc="Alert on bus voltage over limit"),
                bits("BUL", 12, reset=0, desc="Alert on bus voltage under limit"),
                bits("POL", 11, reset=0, desc="Alert on power over limit"),
                bits("CNVR", 10, reset=0, desc="Alert on conversion ready"),
                bits("AFF", 4, access=Access.RO, reset=0, desc="Alert function flag"),
                bits("CVRF", 3, access=Access.RO, reset=0, desc="Conversion ready flag"),
                bits("OVF", 2, access=Access.RO, reset=0, desc="Math overflow flag"),
                bits("APOL", 1, reset=0, desc="Alert polarity. 0 = active low (default)."),
                bits("LEN", 0, reset=0, desc="Alert latch enable"),
            ],
        ),
        reg("ALERT_LIMIT", 0x07, size=16, reset=0x0000,
            desc="Threshold compared against whichever alert source MASK_ENABLE selects"),
        reg("MANUFACTURER_ID", 0xFE, size=16, access=Access.RO, reset=0x5449,
            desc="Manufacturer ID. Reads 0x5449, which is 'TI' in ASCII."),
        reg("DIE_ID", 0xFF, size=16, access=Access.RO, reset=0x2260,
            desc="Die ID and revision. Reads 0x2260."),
    ]

    return make_record(
        part_number="INA226",
        manufacturer="Texas Instruments",
        description="Bidirectional current and power monitor with alert and I2C",
        buses=[Bus.I2C],
        i2c_addresses=list(range(0x40, 0x50)),
        registers=registers,
        source="TI INA226 datasheet (SBOS547)",
    )
