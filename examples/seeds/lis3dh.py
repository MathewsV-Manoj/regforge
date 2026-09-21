"""STMicroelectronics LIS3DH -- 3-axis accelerometer, I2C and SPI.

Two things in this map catch people out. CTRL_REG1 resets with the three axis
enables set but ODR at 0b0000, which is power-down, so the part is configured
and silent. And multi-byte reads require the MSB of the sub-address to be set
for auto-increment, which is a bus-protocol detail rather than a register --
noted here because generated drivers need to know it.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, data_regs, make_record, reg

ODR = [
    EnumValue(name="POWER_DOWN", value=0b0000, description="Power down (default)"),
    EnumValue(name="HZ_1", value=0b0001, description="1 Hz"),
    EnumValue(name="HZ_10", value=0b0010, description="10 Hz"),
    EnumValue(name="HZ_25", value=0b0011, description="25 Hz"),
    EnumValue(name="HZ_50", value=0b0100, description="50 Hz"),
    EnumValue(name="HZ_100", value=0b0101, description="100 Hz"),
    EnumValue(name="HZ_200", value=0b0110, description="200 Hz"),
    EnumValue(name="HZ_400", value=0b0111, description="400 Hz"),
    EnumValue(name="LP_1620", value=0b1000, description="1.62 kHz, low-power mode only"),
    EnumValue(name="HZ_5376", value=0b1001, description="5.376 kHz low-power / 1.344 kHz normal"),
]

FS = [
    EnumValue(name="G_2", value=0b00, description="+/-2 g (default)"),
    EnumValue(name="G_4", value=0b01, description="+/-4 g"),
    EnumValue(name="G_8", value=0b10, description="+/-8 g"),
    EnumValue(name="G_16", value=0b11, description="+/-16 g"),
]


def build_record():
    registers = [
        reg("STATUS_REG_AUX", 0x07, access=Access.RO,
            desc="ADC data-ready and overrun flags"),
        reg("OUT_ADC1_L", 0x08, access=Access.RO, desc="ADC channel 1, low byte"),
        reg("OUT_ADC1_H", 0x09, access=Access.RO, desc="ADC channel 1, high byte"),
        reg("OUT_ADC2_L", 0x0A, access=Access.RO, desc="ADC channel 2, low byte"),
        reg("OUT_ADC2_H", 0x0B, access=Access.RO, desc="ADC channel 2, high byte"),
        reg("OUT_ADC3_L", 0x0C, access=Access.RO, desc="ADC channel 3, low byte"),
        reg("OUT_ADC3_H", 0x0D, access=Access.RO, desc="ADC channel 3, high byte"),
        reg("WHO_AM_I", 0x0F, access=Access.RO, reset=0x33,
            desc="Device identification. Always reads 0x33."),
        reg(
            "CTRL_REG0", 0x1E, reset=0x10,
            desc="SDO/SA0 pull-up control. The reserved bits must be written as 0b0010000.",
            fields=[bits("SDO_PU_DISC", 7, reset=0, desc="1 disconnects the SDO/SA0 pull-up")],
        ),
        reg("TEMP_CFG_REG", 0x1F, reset=0x00,
            desc="Temperature sensor and ADC enable",
            fields=[
                bits("ADC_EN", 7, reset=0, desc="Enable the auxiliary ADC"),
                bits("TEMP_EN", 6, reset=0, desc="Enable the temperature sensor"),
            ]),
        reg(
            "CTRL_REG1", 0x20, reset=0x07,
            desc="Output data rate, low-power mode and axis enables. Note the reset value: "
                 "all three axes are enabled but ODR is power-down, so the part produces "
                 "nothing until you set a rate.",
            fields=[
                bits("ODR", 4, 4, reset=0b0000, desc="Output data rate", enums=ODR),
                bits("LPEN", 3, reset=0, desc="Low-power mode enable (8-bit data)"),
                bits("ZEN", 2, reset=1, desc="Z-axis enable"),
                bits("YEN", 1, reset=1, desc="Y-axis enable"),
                bits("XEN", 0, reset=1, desc="X-axis enable"),
            ],
        ),
        reg(
            "CTRL_REG2", 0x21, reset=0x00,
            desc="High-pass filter configuration",
            fields=[
                bits("HPM", 6, 2, reset=0b00, desc="High-pass filter mode"),
                bits("HPCF", 4, 2, reset=0b00, desc="High-pass filter cutoff frequency"),
                bits("FDS", 3, reset=0, desc="Filtered data selection"),
                bits("HPCLICK", 2, reset=0, desc="High-pass filter enabled for click"),
                bits("HP_IA2", 1, reset=0, desc="High-pass filter enabled for interrupt 2"),
                bits("HP_IA1", 0, reset=0, desc="High-pass filter enabled for interrupt 1"),
            ],
        ),
        reg(
            "CTRL_REG3", 0x22, reset=0x00,
            desc="INT1 pin routing",
            fields=[
                bits("I1_CLICK", 7, reset=0, desc="Click interrupt on INT1"),
                bits("I1_IA1", 6, reset=0, desc="IA1 interrupt on INT1"),
                bits("I1_IA2", 5, reset=0, desc="IA2 interrupt on INT1"),
                bits("I1_ZYXDA", 4, reset=0, desc="Data ready on INT1"),
                bits("I1_321DA", 3, reset=0, desc="ADC data ready on INT1"),
                bits("I1_WTM", 2, reset=0, desc="FIFO watermark on INT1"),
                bits("I1_OVERRUN", 1, reset=0, desc="FIFO overrun on INT1"),
            ],
        ),
        reg(
            "CTRL_REG4", 0x23, reset=0x00,
            desc="Scale, resolution and SPI mode",
            fields=[
                bits("BDU", 7, reset=0,
                     desc="Block data update. Set it, or the high and low bytes of a sample can "
                          "come from different measurements."),
                bits("BLE", 6, reset=0, desc="Big/little endian selection"),
                bits("FS", 4, 2, reset=0b00, desc="Full-scale selection", enums=FS),
                bits("HR", 3, reset=0, desc="High-resolution output mode (12-bit)"),
                bits("ST", 1, 2, reset=0b00, desc="Self-test enable"),
                bits("SIM", 0, reset=0, desc="SPI serial interface mode. 1 = 3-wire."),
            ],
        ),
        reg(
            "CTRL_REG5", 0x24, reset=0x00,
            desc="Memory reboot, FIFO and interrupt latching",
            fields=[
                bits("BOOT", 7, access=Access.W1P, reset=0, desc="Reboot memory content; self-clearing"),
                bits("FIFO_EN", 6, reset=0, desc="FIFO enable"),
                bits("LIR_INT1", 3, reset=0, desc="Latch interrupt request on INT1"),
                bits("D4D_INT1", 2, reset=0, desc="4D detection enabled on INT1"),
                bits("LIR_INT2", 1, reset=0, desc="Latch interrupt request on INT2"),
                bits("D4D_INT2", 0, reset=0, desc="4D detection enabled on INT2"),
            ],
        ),
        reg(
            "CTRL_REG6", 0x25, reset=0x00,
            desc="INT2 pin routing and interrupt polarity",
            fields=[
                bits("I2_CLICK", 7, reset=0, desc="Click interrupt on INT2"),
                bits("I2_IA1", 6, reset=0, desc="IA1 interrupt on INT2"),
                bits("I2_IA2", 5, reset=0, desc="IA2 interrupt on INT2"),
                bits("I2_BOOT", 4, reset=0, desc="Boot status on INT2"),
                bits("I2_ACT", 3, reset=0, desc="Activity interrupt on INT2"),
                bits("INT_POLARITY", 1, reset=0, desc="0 = active high, 1 = active low"),
            ],
        ),
        reg("REFERENCE", 0x26, reset=0x00,
            desc="Reference value for interrupt generation"),
        reg(
            "STATUS_REG", 0x27, access=Access.RO, reset=0x00,
            desc="Acceleration data status",
            fields=[
                bits("ZYXOR", 7, access=Access.RO, reset=0, desc="X, Y and Z data overrun"),
                bits("ZOR", 6, access=Access.RO, reset=0, desc="Z data overrun"),
                bits("YOR", 5, access=Access.RO, reset=0, desc="Y data overrun"),
                bits("XOR_", 4, access=Access.RO, reset=0, desc="X data overrun"),
                bits("ZYXDA", 3, access=Access.RO, reset=0, desc="X, Y and Z new data available"),
                bits("ZDA", 2, access=Access.RO, reset=0, desc="Z new data available"),
                bits("YDA", 1, access=Access.RO, reset=0, desc="Y new data available"),
                bits("XDA", 0, access=Access.RO, reset=0, desc="X new data available"),
            ],
        ),
        reg(
            "FIFO_CTRL_REG", 0x2E, reset=0x00,
            desc="FIFO mode and threshold",
            fields=[
                bits(
                    "FM", 6, 2, reset=0b00,
                    desc="FIFO mode",
                    enums=[
                        EnumValue(name="BYPASS", value=0b00, description="Bypass mode (default)"),
                        EnumValue(name="FIFO", value=0b01, description="FIFO mode"),
                        EnumValue(name="STREAM", value=0b10, description="Stream mode"),
                        EnumValue(name="STREAM_TO_FIFO", value=0b11, description="Stream-to-FIFO mode"),
                    ],
                ),
                bits("TR", 5, reset=0, desc="Trigger selection. 0 = INT1, 1 = INT2."),
                bits("FTH", 0, 5, reset=0, desc="FIFO threshold"),
            ],
        ),
        reg(
            "FIFO_SRC_REG", 0x2F, access=Access.RO,
            desc="FIFO status",
            fields=[
                bits("WTM", 7, access=Access.RO, desc="Watermark level reached"),
                bits("OVRN_FIFO", 6, access=Access.RO, desc="FIFO overrun"),
                bits("EMPTY", 5, access=Access.RO, desc="FIFO is empty"),
                bits("FSS", 0, 5, access=Access.RO, desc="Number of unread samples"),
            ],
        ),
        reg("INT1_CFG", 0x30, reset=0x00, desc="Interrupt 1 configuration"),
        reg("INT1_SRC", 0x31, access=Access.RO, reset=0x00, desc="Interrupt 1 source. Cleared on read."),
        reg("INT1_THS", 0x32, reset=0x00, desc="Interrupt 1 threshold"),
        reg("INT1_DURATION", 0x33, reset=0x00, desc="Interrupt 1 duration"),
        reg("INT2_CFG", 0x34, reset=0x00, desc="Interrupt 2 configuration"),
        reg("INT2_SRC", 0x35, access=Access.RO, reset=0x00, desc="Interrupt 2 source. Cleared on read."),
        reg("INT2_THS", 0x36, reset=0x00, desc="Interrupt 2 threshold"),
        reg("INT2_DURATION", 0x37, reset=0x00, desc="Interrupt 2 duration"),
        reg("CLICK_CFG", 0x38, reset=0x00, desc="Click detection configuration"),
        reg("CLICK_SRC", 0x39, access=Access.RO, reset=0x00, desc="Click detection source"),
        reg("CLICK_THS", 0x3A, reset=0x00, desc="Click threshold"),
        reg("TIME_LIMIT", 0x3B, reset=0x00, desc="Click time limit"),
        reg("TIME_LATENCY", 0x3C, reset=0x00, desc="Click time latency"),
        reg("TIME_WINDOW", 0x3D, reset=0x00, desc="Click time window"),
    ]

    registers += data_regs(
        [
            ("OUT_X_L", 0x28, None, "X-axis acceleration, low byte"),
            ("OUT_X_H", 0x29, None, "X-axis acceleration, high byte"),
            ("OUT_Y_L", 0x2A, None, "Y-axis acceleration, low byte"),
            ("OUT_Y_H", 0x2B, None, "Y-axis acceleration, high byte"),
            ("OUT_Z_L", 0x2C, None, "Z-axis acceleration, low byte"),
            ("OUT_Z_H", 0x2D, None, "Z-axis acceleration, high byte"),
        ]
    )

    return make_record(
        part_number="LIS3DH",
        manufacturer="STMicroelectronics",
        description="3-axis MEMS accelerometer with FIFO, click and 4D detection",
        buses=[Bus.I2C, Bus.SPI],
        i2c_addresses=[0x18, 0x19],  # SDO/SA0 low / high
        registers=registers,
        source="ST LIS3DH datasheet",
        notes=(
            "Hand-authored seed entry, not machine-extracted. Multi-byte reads require the "
            "MSB of the sub-address to be set for auto-increment; that is a bus-protocol "
            "detail rather than a register and is not modelled here. Check against the "
            "datasheet before trusting it, then mark it verified."
        ),
    )
