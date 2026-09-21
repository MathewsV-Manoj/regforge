"""Maxim/ADI DS1307 -- serial real-time clock with 56 bytes of NVRAM.

Seeded beside the DS3231 because they are constantly confused. Same I2C
address, overlapping register layout, but the DS1307 has CH (clock halt) in
bit 7 of SECONDS -- a bit the DS3231 does not have, and the single most common
reason a new DS1307 appears dead: it ships with the oscillator stopped.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, make_record, reg


def build_record():
    registers = [
        reg(
            "SECONDS", 0x00,
            desc="Seconds in BCD, plus the clock halt bit",
            fields=[
                bits("CH", 7,
                     desc="Clock halt. 1 stops the oscillator. Set on a new part, so clear it "
                          "before the clock will run."),
                bits("SECONDS_10", 4, 3, desc="Tens of seconds, 0-5"),
                bits("SECONDS_1", 0, 4, desc="Units of seconds, 0-9"),
            ],
        ),
        reg(
            "MINUTES", 0x01,
            desc="Minutes in BCD, 00-59",
            fields=[
                bits("MINUTES_10", 4, 3, desc="Tens of minutes, 0-5"),
                bits("MINUTES_1", 0, 4, desc="Units of minutes, 0-9"),
            ],
        ),
        reg(
            "HOURS", 0x02,
            desc="Hours in BCD. Layout depends on the 12/24 bit.",
            fields=[
                bits(
                    "MODE_12_24", 6,
                    desc="0 = 24-hour mode, 1 = 12-hour mode",
                    enums=[
                        EnumValue(name="MODE_24H", value=0, description="24-hour format"),
                        EnumValue(name="MODE_12H", value=1, description="12-hour format, bit 5 is AM/PM"),
                    ],
                ),
                bits("AM_PM_HOUR_20", 5,
                     desc="In 12-hour mode: 0 = AM, 1 = PM. In 24-hour mode: the 20-hour bit."),
                bits("HOURS_10", 4, desc="The 10-hour bit"),
                bits("HOURS_1", 0, 4, desc="Units of hours, 0-9"),
            ],
        ),
        reg("DAY", 0x03, desc="Day of week, 1-7, defined by the user",
            fields=[bits("DAY", 0, 3, desc="Day of week, 1-7")]),
        reg(
            "DATE", 0x04,
            desc="Day of month in BCD, 01-31",
            fields=[
                bits("DATE_10", 4, 2, desc="Tens of the date, 0-3"),
                bits("DATE_1", 0, 4, desc="Units of the date, 0-9"),
            ],
        ),
        reg(
            "MONTH", 0x05,
            desc="Month in BCD, 01-12",
            fields=[
                bits("MONTH_10", 4, desc="Tens of the month"),
                bits("MONTH_1", 0, 4, desc="Units of the month, 0-9"),
            ],
        ),
        reg(
            "YEAR", 0x06,
            desc="Year within the century in BCD, 00-99",
            fields=[
                bits("YEAR_10", 4, 4, desc="Tens of the year"),
                bits("YEAR_1", 0, 4, desc="Units of the year"),
            ],
        ),
        reg(
            "CONTROL", 0x07, reset=0x03,
            desc="Square-wave output control",
            fields=[
                bits("OUT", 7, reset=0,
                     desc="Output level on SQW/OUT when SQWE is 0"),
                bits("SQWE", 4, reset=0, desc="Square-wave enable"),
                bits(
                    "RS", 0, 2, reset=0b11,
                    desc="Square-wave rate select",
                    enums=[
                        EnumValue(name="HZ_1", value=0b00, description="1 Hz"),
                        EnumValue(name="KHZ_4_096", value=0b01, description="4.096 kHz"),
                        EnumValue(name="KHZ_8_192", value=0b10, description="8.192 kHz"),
                        EnumValue(name="KHZ_32_768", value=0b11, description="32.768 kHz (default)"),
                    ],
                ),
            ],
        ),
    ]

    return make_record(
        part_number="DS1307",
        manufacturer="Analog Devices",
        description="I2C real-time clock with 56 bytes of battery-backed NVRAM",
        buses=[Bus.I2C],
        i2c_addresses=[0x68],
        registers=registers,
        source="Maxim/ADI DS1307 datasheet",
        notes=(
            "Hand-authored seed entry, not machine-extracted. Timekeeping registers carry no "
            "reset value because the datasheet states none -- they hold whatever the backup "
            "battery preserved. The 56 bytes of NVRAM at 0x08-0x3F are plain memory rather "
            "than registers and are not modelled. Check against the datasheet before trusting "
            "it, then mark it verified."
        ),
    )
