"""Analog Devices ADXL345 -- 3-axis accelerometer, I2C and SPI.

One of the most-used accelerometers in hobby and product work, and a good
corpus entry because DATA_FORMAT and POWER_CTL are the two registers people
get wrong: FULL_RES changes the scaling silently, and the device boots in
standby with Measure clear.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, data_regs, make_record, reg

RATE = [
    EnumValue(name="HZ_0_10", value=0b0000, description="0.10 Hz"),
    EnumValue(name="HZ_0_20", value=0b0001, description="0.20 Hz"),
    EnumValue(name="HZ_0_39", value=0b0010, description="0.39 Hz"),
    EnumValue(name="HZ_0_78", value=0b0011, description="0.78 Hz"),
    EnumValue(name="HZ_1_56", value=0b0100, description="1.56 Hz"),
    EnumValue(name="HZ_3_13", value=0b0101, description="3.13 Hz"),
    EnumValue(name="HZ_6_25", value=0b0110, description="6.25 Hz"),
    EnumValue(name="HZ_12_5", value=0b0111, description="12.5 Hz"),
    EnumValue(name="HZ_25", value=0b1000, description="25 Hz"),
    EnumValue(name="HZ_50", value=0b1001, description="50 Hz"),
    EnumValue(name="HZ_100", value=0b1010, description="100 Hz (default)"),
    EnumValue(name="HZ_200", value=0b1011, description="200 Hz"),
    EnumValue(name="HZ_400", value=0b1100, description="400 Hz"),
    EnumValue(name="HZ_800", value=0b1101, description="800 Hz"),
    EnumValue(name="HZ_1600", value=0b1110, description="1600 Hz"),
    EnumValue(name="HZ_3200", value=0b1111, description="3200 Hz"),
]

RANGE = [
    EnumValue(name="G_2", value=0b00, description="+/-2 g (default)"),
    EnumValue(name="G_4", value=0b01, description="+/-4 g"),
    EnumValue(name="G_8", value=0b10, description="+/-8 g"),
    EnumValue(name="G_16", value=0b11, description="+/-16 g"),
]


def build_record():
    registers = [
        reg("DEVID", 0x00, access=Access.RO, reset=0xE5,
            desc="Device ID. Always reads 0xE5."),
        reg("THRESH_TAP", 0x1D, desc="Tap threshold, 62.5 mg per LSB"),
        reg("OFSX", 0x1E, desc="X-axis offset, two's complement, 15.6 mg per LSB"),
        reg("OFSY", 0x1F, desc="Y-axis offset, two's complement, 15.6 mg per LSB"),
        reg("OFSZ", 0x20, desc="Z-axis offset, two's complement, 15.6 mg per LSB"),
        reg("DUR", 0x21, desc="Maximum tap duration, 625 us per LSB"),
        reg("LATENT", 0x22, desc="Tap latency, 1.25 ms per LSB"),
        reg("WINDOW", 0x23, desc="Double-tap window, 1.25 ms per LSB"),
        reg("THRESH_ACT", 0x24, desc="Activity threshold, 62.5 mg per LSB"),
        reg("THRESH_INACT", 0x25, desc="Inactivity threshold, 62.5 mg per LSB"),
        reg("TIME_INACT", 0x26, desc="Inactivity time, 1 s per LSB"),
        reg(
            "ACT_INACT_CTL", 0x27, reset=0x00,
            desc="Axis enables for activity and inactivity detection",
            fields=[
                bits("ACT_AC_DC", 7, reset=0, desc="Activity: 0 = dc-coupled, 1 = ac-coupled"),
                bits("ACT_X_EN", 6, reset=0, desc="Enable X for activity"),
                bits("ACT_Y_EN", 5, reset=0, desc="Enable Y for activity"),
                bits("ACT_Z_EN", 4, reset=0, desc="Enable Z for activity"),
                bits("INACT_AC_DC", 3, reset=0, desc="Inactivity: 0 = dc-coupled, 1 = ac-coupled"),
                bits("INACT_X_EN", 2, reset=0, desc="Enable X for inactivity"),
                bits("INACT_Y_EN", 1, reset=0, desc="Enable Y for inactivity"),
                bits("INACT_Z_EN", 0, reset=0, desc="Enable Z for inactivity"),
            ],
        ),
        reg("THRESH_FF", 0x28, desc="Free-fall threshold, 62.5 mg per LSB"),
        reg("TIME_FF", 0x29, desc="Free-fall time, 5 ms per LSB"),
        reg(
            "TAP_AXES", 0x2A, reset=0x00,
            desc="Axis enables for tap detection",
            fields=[
                bits("SUPPRESS", 3, reset=0, desc="Suppress double tap if a spike occurs during latency"),
                bits("TAP_X_EN", 2, reset=0, desc="Enable X for tap"),
                bits("TAP_Y_EN", 1, reset=0, desc="Enable Y for tap"),
                bits("TAP_Z_EN", 0, reset=0, desc="Enable Z for tap"),
            ],
        ),
        reg(
            "ACT_TAP_STATUS", 0x2B, access=Access.RO, reset=0x00,
            desc="Which axis was involved in the most recent event",
            fields=[
                bits("ACT_X_SRC", 6, access=Access.RO, reset=0, desc="X involved in activity"),
                bits("ACT_Y_SRC", 5, access=Access.RO, reset=0, desc="Y involved in activity"),
                bits("ACT_Z_SRC", 4, access=Access.RO, reset=0, desc="Z involved in activity"),
                bits("ASLEEP", 3, access=Access.RO, reset=0, desc="Device is in sleep mode"),
                bits("TAP_X_SRC", 2, access=Access.RO, reset=0, desc="X involved in tap"),
                bits("TAP_Y_SRC", 1, access=Access.RO, reset=0, desc="Y involved in tap"),
                bits("TAP_Z_SRC", 0, access=Access.RO, reset=0, desc="Z involved in tap"),
            ],
        ),
        reg(
            "BW_RATE", 0x2C, reset=0x0A,
            desc="Output data rate and low-power mode",
            fields=[
                bits("LOW_POWER", 4, reset=0, desc="Reduced power at the cost of higher noise"),
                bits("RATE", 0, 4, reset=0b1010, desc="Output data rate", enums=RATE),
            ],
        ),
        reg(
            "POWER_CTL", 0x2D, reset=0x00,
            desc="Power-saving control. Measure is clear at reset, so the part boots in "
                 "standby and produces no data until you set it.",
            fields=[
                bits("LINK", 5, reset=0, desc="Serially link activity and inactivity detection"),
                bits("AUTO_SLEEP", 4, reset=0, desc="Enter sleep automatically on inactivity"),
                bits("MEASURE", 3, reset=0, desc="0 = standby, 1 = measurement. Set this to start."),
                bits("SLEEP", 2, reset=0, desc="Put the part into sleep mode"),
                bits(
                    "WAKEUP", 0, 2, reset=0b00,
                    desc="Reading rate in sleep mode",
                    enums=[
                        EnumValue(name="HZ_8", value=0b00, description="8 Hz"),
                        EnumValue(name="HZ_4", value=0b01, description="4 Hz"),
                        EnumValue(name="HZ_2", value=0b10, description="2 Hz"),
                        EnumValue(name="HZ_1", value=0b11, description="1 Hz"),
                    ],
                ),
            ],
        ),
        reg(
            "INT_ENABLE", 0x2E, reset=0x00,
            desc="Interrupt enables",
            fields=[
                bits("DATA_READY", 7, reset=0, desc="Data ready"),
                bits("SINGLE_TAP", 6, reset=0, desc="Single tap"),
                bits("DOUBLE_TAP", 5, reset=0, desc="Double tap"),
                bits("ACTIVITY", 4, reset=0, desc="Activity"),
                bits("INACTIVITY", 3, reset=0, desc="Inactivity"),
                bits("FREE_FALL", 2, reset=0, desc="Free fall"),
                bits("WATERMARK", 1, reset=0, desc="FIFO watermark"),
                bits("OVERRUN", 0, reset=0, desc="FIFO overrun"),
            ],
        ),
        reg(
            "INT_MAP", 0x2F, reset=0x00,
            desc="Interrupt routing. 0 sends the event to INT1, 1 sends it to INT2.",
            fields=[
                bits("DATA_READY", 7, reset=0, desc="Route data ready"),
                bits("SINGLE_TAP", 6, reset=0, desc="Route single tap"),
                bits("DOUBLE_TAP", 5, reset=0, desc="Route double tap"),
                bits("ACTIVITY", 4, reset=0, desc="Route activity"),
                bits("INACTIVITY", 3, reset=0, desc="Route inactivity"),
                bits("FREE_FALL", 2, reset=0, desc="Route free fall"),
                bits("WATERMARK", 1, reset=0, desc="Route FIFO watermark"),
                bits("OVERRUN", 0, reset=0, desc="Route FIFO overrun"),
            ],
        ),
        reg(
            "INT_SOURCE", 0x30, access=Access.RO, reset=0x02,
            desc="Which interrupts are asserted. Reading clears most of them.",
            fields=[
                bits("DATA_READY", 7, access=Access.RO, reset=0, desc="Data ready"),
                bits("SINGLE_TAP", 6, access=Access.RO, reset=0, desc="Single tap"),
                bits("DOUBLE_TAP", 5, access=Access.RO, reset=0, desc="Double tap"),
                bits("ACTIVITY", 4, access=Access.RO, reset=0, desc="Activity"),
                bits("INACTIVITY", 3, access=Access.RO, reset=0, desc="Inactivity"),
                bits("FREE_FALL", 2, access=Access.RO, reset=0, desc="Free fall"),
                bits("WATERMARK", 1, access=Access.RO, reset=1, desc="FIFO watermark"),
                bits("OVERRUN", 0, access=Access.RO, reset=0, desc="FIFO overrun"),
            ],
        ),
        reg(
            "DATA_FORMAT", 0x31, reset=0x00,
            desc="Data presentation. FULL_RES changes how the 13-bit result is aligned, "
                 "which is the usual cause of scaling that looks wrong by a factor of 2.",
            fields=[
                bits("SELF_TEST", 7, reset=0, desc="Apply a self-test force to the sensor"),
                bits("SPI", 6, reset=0, desc="0 = 4-wire SPI, 1 = 3-wire SPI"),
                bits("INT_INVERT", 5, reset=0, desc="0 = interrupts active high, 1 = active low"),
                bits("FULL_RES", 3, reset=0,
                     desc="1 = full resolution, 4 mg per LSB at every range. 0 = fixed 10-bit."),
                bits("JUSTIFY", 2, reset=0, desc="1 = left-justified (MSB) mode"),
                bits("RANGE", 0, 2, reset=0b00, desc="g range", enums=RANGE),
            ],
        ),
        reg(
            "FIFO_CTL", 0x38, reset=0x00,
            desc="FIFO mode and watermark",
            fields=[
                bits(
                    "FIFO_MODE", 6, 2, reset=0b00,
                    desc="FIFO mode",
                    enums=[
                        EnumValue(name="BYPASS", value=0b00, description="FIFO bypassed (default)"),
                        EnumValue(name="FIFO", value=0b01, description="Collect until full, then stop"),
                        EnumValue(name="STREAM", value=0b10, description="Keep the most recent 32 samples"),
                        EnumValue(name="TRIGGER", value=0b11, description="Hold samples around a trigger event"),
                    ],
                ),
                bits("TRIGGER", 5, reset=0, desc="0 = trigger on INT1, 1 = trigger on INT2"),
                bits("SAMPLES", 0, 5, reset=0, desc="Watermark sample count"),
            ],
        ),
        reg(
            "FIFO_STATUS", 0x39, access=Access.RO, reset=0x00,
            desc="FIFO fill level",
            fields=[
                bits("FIFO_TRIG", 7, access=Access.RO, reset=0, desc="A trigger event has occurred"),
                bits("ENTRIES", 0, 6, access=Access.RO, reset=0, desc="Number of samples in the FIFO"),
            ],
        ),
    ]

    registers += data_regs(
        [
            ("DATAX0", 0x32, None, "X-axis measurement, low byte"),
            ("DATAX1", 0x33, None, "X-axis measurement, high byte"),
            ("DATAY0", 0x34, None, "Y-axis measurement, low byte"),
            ("DATAY1", 0x35, None, "Y-axis measurement, high byte"),
            ("DATAZ0", 0x36, None, "Z-axis measurement, low byte"),
            ("DATAZ1", 0x37, None, "Z-axis measurement, high byte"),
        ]
    )

    return make_record(
        part_number="ADXL345",
        manufacturer="Analog Devices",
        description="3-axis MEMS accelerometer with tap, activity and free-fall detection",
        buses=[Bus.I2C, Bus.SPI],
        i2c_addresses=[0x53, 0x1D],  # ALT ADDRESS pin low / high
        registers=registers,
        source="Analog Devices ADXL345 datasheet",
    )
