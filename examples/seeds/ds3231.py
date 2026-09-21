"""Maxim/ADI DS3231 -- temperature-compensated real-time clock.

A useful seed because most of it honestly has no reset value. The timekeeping
registers hold whatever the backup battery preserved, so they are transcribed
with `reset_value = None` rather than a fabricated 0x00. That is the rule the
extractor is given, applied to hand-authored data.

The time and date fields are BCD. That is recorded in the descriptions; the
schema deliberately does not model numeric encodings, because pretending to
know an encoding is how a generator produces confidently wrong accessors.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, make_record, reg

RS = [
    EnumValue(name="HZ_1", value=0b00, description="1 Hz"),
    EnumValue(name="KHZ_1_024", value=0b01, description="1.024 kHz"),
    EnumValue(name="KHZ_4_096", value=0b10, description="4.096 kHz"),
    EnumValue(name="KHZ_8_192", value=0b11, description="8.192 kHz (default)"),
]


def build_record():
    registers = [
        reg(
            "SECONDS",
            0x00,
            desc="Seconds, BCD, 00-59",
            fields=[
                bits("SECONDS_10", 4, 3, desc="Tens of seconds, 0-5"),
                bits("SECONDS_1", 0, 4, desc="Units of seconds, 0-9"),
            ],
        ),
        reg(
            "MINUTES",
            0x01,
            desc="Minutes, BCD, 00-59",
            fields=[
                bits("MINUTES_10", 4, 3, desc="Tens of minutes, 0-5"),
                bits("MINUTES_1", 0, 4, desc="Units of minutes, 0-9"),
            ],
        ),
        reg(
            "HOURS",
            0x02,
            desc="Hours, BCD. Format depends on the 12/24 bit.",
            fields=[
                bits(
                    "MODE_12_24",
                    6,
                    desc="0 = 24-hour mode, 1 = 12-hour mode",
                    enums=[
                        EnumValue(name="MODE_24H", value=0, description="24-hour format"),
                        EnumValue(name="MODE_12H", value=1, description="12-hour format, bit 5 is AM/PM"),
                    ],
                ),
                bits("AM_PM_HOUR_20", 5, desc="In 12-hour mode: 0 = AM, 1 = PM. In 24-hour mode: the 20-hour bit."),
                bits("HOURS_10", 4, desc="The 10-hour bit"),
                bits("HOURS_1", 0, 4, desc="Units of hours, 0-9"),
            ],
        ),
        reg("DAY", 0x03, desc="Day of week, 1-7. Defined by the user and incremented at midnight.",
            fields=[bits("DAY", 0, 3, desc="Day of week, 1-7")]),
        reg(
            "DATE",
            0x04,
            desc="Day of month, BCD, 01-31",
            fields=[
                bits("DATE_10", 4, 2, desc="Tens of the date, 0-3"),
                bits("DATE_1", 0, 4, desc="Units of the date, 0-9"),
            ],
        ),
        reg(
            "MONTH_CENTURY",
            0x05,
            desc="Month in BCD, plus the century flag",
            fields=[
                bits("CENTURY", 7, desc="Toggles when the year counter overflows from 99 to 00"),
                bits("MONTH_10", 4, desc="Tens of the month"),
                bits("MONTH_1", 0, 4, desc="Units of the month, 0-9"),
            ],
        ),
        reg(
            "YEAR",
            0x06,
            desc="Year within the century, BCD, 00-99",
            fields=[
                bits("YEAR_10", 4, 4, desc="Tens of the year"),
                bits("YEAR_1", 0, 4, desc="Units of the year"),
            ],
        ),
        reg("ALARM1_SECONDS", 0x07, desc="Alarm 1 seconds, BCD, with the A1M1 mask in bit 7",
            fields=[bits("A1M1", 7, desc="Alarm 1 mask bit 1")]),
        reg("ALARM1_MINUTES", 0x08, desc="Alarm 1 minutes, BCD, with the A1M2 mask in bit 7",
            fields=[bits("A1M2", 7, desc="Alarm 1 mask bit 2")]),
        reg("ALARM1_HOURS", 0x09, desc="Alarm 1 hours, BCD, with the A1M3 mask in bit 7",
            fields=[bits("A1M3", 7, desc="Alarm 1 mask bit 3")]),
        reg(
            "ALARM1_DAY_DATE",
            0x0A,
            desc="Alarm 1 day or date, selected by DY/DT",
            fields=[
                bits("A1M4", 7, desc="Alarm 1 mask bit 4"),
                bits("DY_DT", 6, desc="0 = match the date, 1 = match the day of week"),
            ],
        ),
        reg("ALARM2_MINUTES", 0x0B, desc="Alarm 2 minutes, BCD, with the A2M2 mask in bit 7",
            fields=[bits("A2M2", 7, desc="Alarm 2 mask bit 2")]),
        reg("ALARM2_HOURS", 0x0C, desc="Alarm 2 hours, BCD, with the A2M3 mask in bit 7",
            fields=[bits("A2M3", 7, desc="Alarm 2 mask bit 3")]),
        reg(
            "ALARM2_DAY_DATE",
            0x0D,
            desc="Alarm 2 day or date, selected by DY/DT",
            fields=[
                bits("A2M4", 7, desc="Alarm 2 mask bit 4"),
                bits("DY_DT", 6, desc="0 = match the date, 1 = match the day of week"),
            ],
        ),
        reg(
            "CONTROL",
            0x0E,
            reset=0x1C,
            desc="Oscillator, square wave and alarm interrupt control",
            fields=[
                bits("EOSC", 7, reset=0, desc="Enable oscillator, active low. 0 = oscillator runs on battery."),
                bits("BBSQW", 6, reset=0, desc="Battery-backed square wave enable"),
                bits("CONV", 5, access=Access.W1P, reset=0, desc="Force a temperature conversion; self-clearing"),
                bits("RS2", 4, reset=1, desc="Square wave rate select, high bit"),
                bits("RS1", 3, reset=1, desc="Square wave rate select, low bit"),
                bits("INTCN", 2, reset=1, desc="Interrupt control. 1 = INT/SQW outputs alarm interrupts."),
                bits("A2IE", 1, reset=0, desc="Alarm 2 interrupt enable"),
                bits("A1IE", 0, reset=0, desc="Alarm 1 interrupt enable"),
            ],
        ),
        reg(
            "STATUS",
            0x0F,
            desc="Oscillator stop flag, 32 kHz output enable and alarm flags",
            fields=[
                bits("OSF", 7, access=Access.RW1C, desc="Oscillator stop flag: the timekeeping data may be invalid"),
                bits("EN32KHZ", 3, reset=1, desc="Enable the 32 kHz output"),
                bits("BSY", 2, access=Access.RO, desc="Busy executing a temperature conversion"),
                bits("A2F", 1, access=Access.RW1C, desc="Alarm 2 flag; write 0 to clear"),
                bits("A1F", 0, access=Access.RW1C, desc="Alarm 1 flag; write 0 to clear"),
            ],
        ),
        reg("AGING_OFFSET", 0x10, desc="Aging offset, two's complement, applied to the oscillator capacitance"),
        reg("TEMP_MSB", 0x11, access=Access.RO, desc="Temperature, integer part, two's complement"),
        reg(
            "TEMP_LSB",
            0x12,
            access=Access.RO,
            desc="Temperature, fractional part in bits [7:6], 0.25 C per LSB",
            fields=[bits("TEMP_FRACTION", 6, 2, access=Access.RO, desc="Fractional temperature, 0.25 C per count")],
        ),
    ]

    return make_record(
        part_number="DS3231",
        manufacturer="Analog Devices",
        description="Extremely accurate I2C real-time clock with integrated TCXO and crystal",
        buses=[Bus.I2C],
        i2c_addresses=[0x68],
        registers=registers,
        source="Maxim/ADI DS3231 datasheet",
        notes=(
            "Hand-authored seed entry, not machine-extracted. Timekeeping registers carry no "
            "reset value because the datasheet states none -- they hold whatever the backup "
            "supply preserved. Time and date fields are BCD. Check against the DS3231 datasheet "
            "before trusting it, then mark it verified."
        ),
    )
