"""InvenSense MPU-6050 -- six-axis gyro and accelerometer.

The one detail worth getting right here is PWR_MGMT_1's reset value of 0x40:
the device wakes up with SLEEP set, so a driver that does not clear it reads
zeros forever. That is precisely the kind of fact a generated map should carry.

The register map below covers configuration, interrupts and measurement output.
The magnetometer-passthrough and DMP register blocks are intentionally absent
rather than half-transcribed.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, data_regs, make_record, reg

FS_SEL = [
    EnumValue(name="DPS_250", value=0b00, description="+/-250 degrees per second"),
    EnumValue(name="DPS_500", value=0b01, description="+/-500 degrees per second"),
    EnumValue(name="DPS_1000", value=0b10, description="+/-1000 degrees per second"),
    EnumValue(name="DPS_2000", value=0b11, description="+/-2000 degrees per second"),
]

AFS_SEL = [
    EnumValue(name="G_2", value=0b00, description="+/-2 g"),
    EnumValue(name="G_4", value=0b01, description="+/-4 g"),
    EnumValue(name="G_8", value=0b10, description="+/-8 g"),
    EnumValue(name="G_16", value=0b11, description="+/-16 g"),
]

CLKSEL = [
    EnumValue(name="INTERNAL_8MHZ", value=0b000, description="Internal 8 MHz oscillator"),
    EnumValue(name="PLL_X_GYRO", value=0b001, description="PLL with X-axis gyro reference (recommended)"),
    EnumValue(name="PLL_Y_GYRO", value=0b010, description="PLL with Y-axis gyro reference"),
    EnumValue(name="PLL_Z_GYRO", value=0b011, description="PLL with Z-axis gyro reference"),
    EnumValue(name="PLL_EXT_32K", value=0b100, description="PLL with external 32.768 kHz reference"),
    EnumValue(name="PLL_EXT_19M", value=0b101, description="PLL with external 19.2 MHz reference"),
    EnumValue(name="STOP", value=0b111, description="Stops the clock and holds the timing generator in reset"),
]


def build_record():
    registers = [
        reg(
            "SMPLRT_DIV",
            0x19,
            reset=0x00,
            desc="Sample rate divider. Sample rate = gyroscope output rate / (1 + SMPLRT_DIV).",
        ),
        reg(
            "CONFIG",
            0x1A,
            reset=0x00,
            desc="External frame synchronisation and digital low-pass filter configuration",
            fields=[
                bits("EXT_SYNC_SET", 3, 3, reset=0, desc="FSYNC pin sampling configuration"),
                bits("DLPF_CFG", 0, 3, reset=0, desc="Digital low-pass filter bandwidth"),
            ],
        ),
        reg(
            "GYRO_CONFIG",
            0x1B,
            reset=0x00,
            desc="Gyroscope self-test and full-scale range",
            fields=[
                bits("XG_ST", 7, reset=0, desc="X-axis gyro self-test"),
                bits("YG_ST", 6, reset=0, desc="Y-axis gyro self-test"),
                bits("ZG_ST", 5, reset=0, desc="Z-axis gyro self-test"),
                bits("FS_SEL", 3, 2, reset=0, desc="Gyroscope full-scale range", enums=FS_SEL),
            ],
        ),
        reg(
            "ACCEL_CONFIG",
            0x1C,
            reset=0x00,
            desc="Accelerometer self-test and full-scale range",
            fields=[
                bits("XA_ST", 7, reset=0, desc="X-axis accelerometer self-test"),
                bits("YA_ST", 6, reset=0, desc="Y-axis accelerometer self-test"),
                bits("ZA_ST", 5, reset=0, desc="Z-axis accelerometer self-test"),
                bits("AFS_SEL", 3, 2, reset=0, desc="Accelerometer full-scale range", enums=AFS_SEL),
            ],
        ),
        reg(
            "FIFO_EN",
            0x23,
            reset=0x00,
            desc="Selects which sensor measurements are loaded into the FIFO",
            fields=[
                bits("TEMP_FIFO_EN", 7, reset=0, desc="Queue TEMP_OUT to the FIFO"),
                bits("XG_FIFO_EN", 6, reset=0, desc="Queue GYRO_XOUT to the FIFO"),
                bits("YG_FIFO_EN", 5, reset=0, desc="Queue GYRO_YOUT to the FIFO"),
                bits("ZG_FIFO_EN", 4, reset=0, desc="Queue GYRO_ZOUT to the FIFO"),
                bits("ACCEL_FIFO_EN", 3, reset=0, desc="Queue all accelerometer output to the FIFO"),
            ],
        ),
        reg(
            "INT_PIN_CFG",
            0x37,
            reset=0x00,
            desc="INT pin behaviour and I2C bypass",
            fields=[
                bits("INT_LEVEL", 7, reset=0, desc="0 = active high, 1 = active low"),
                bits("INT_OPEN", 6, reset=0, desc="0 = push-pull, 1 = open drain"),
                bits("LATCH_INT_EN", 5, reset=0, desc="0 = 50 us pulse, 1 = latched until cleared"),
                bits("INT_RD_CLEAR", 4, reset=0, desc="1 = any read clears the interrupt status"),
                bits("FSYNC_INT_LEVEL", 3, reset=0, desc="FSYNC interrupt active level"),
                bits("FSYNC_INT_EN", 2, reset=0, desc="Enable the FSYNC pin as an interrupt source"),
                bits("I2C_BYPASS_EN", 1, reset=0, desc="Connect the auxiliary I2C bus to the main bus"),
            ],
        ),
        reg(
            "INT_ENABLE",
            0x38,
            reset=0x00,
            desc="Interrupt enables",
            fields=[
                bits("FIFO_OFLOW_EN", 4, reset=0, desc="Interrupt on FIFO overflow"),
                bits("I2C_MST_INT_EN", 3, reset=0, desc="Interrupt on I2C master events"),
                bits("DATA_RDY_EN", 0, reset=0, desc="Interrupt when new sensor data is available"),
            ],
        ),
        reg(
            "INT_STATUS",
            0x3A,
            access=Access.RO,
            reset=0x00,
            desc="Interrupt status. Cleared on read.",
            fields=[
                bits("FIFO_OFLOW_INT", 4, access=Access.RO, reset=0, desc="FIFO overflow occurred"),
                bits("I2C_MST_INT", 3, access=Access.RO, reset=0, desc="I2C master interrupt"),
                bits("DATA_RDY_INT", 0, access=Access.RO, reset=0, desc="New sensor data is available"),
            ],
        ),
        reg(
            "PWR_MGMT_1",
            0x6B,
            reset=0x40,
            desc="Power mode and clock source. Note the reset value: SLEEP is set, so the device "
            "must be woken before it will produce data.",
            fields=[
                bits("DEVICE_RESET", 7, access=Access.W1P, reset=0, desc="Write 1 to reset all registers; self-clearing"),
                bits("SLEEP", 6, reset=1, desc="Sleep mode. Set at reset -- clear it to start measuring."),
                bits("CYCLE", 5, reset=0, desc="Cycle between sleep and a single sample at LP_WAKE_CTRL rate"),
                bits("TEMP_DIS", 3, reset=0, desc="Disable the temperature sensor"),
                bits("CLKSEL", 0, 3, reset=0, desc="Clock source select", enums=CLKSEL),
            ],
        ),
        reg(
            "PWR_MGMT_2",
            0x6C,
            reset=0x00,
            desc="Low-power wake rate and per-axis standby",
            fields=[
                bits("LP_WAKE_CTRL", 6, 2, reset=0, desc="Wake-up frequency in accelerometer-only low-power mode"),
                bits("STBY_XA", 5, reset=0, desc="Put the X-axis accelerometer into standby"),
                bits("STBY_YA", 4, reset=0, desc="Put the Y-axis accelerometer into standby"),
                bits("STBY_ZA", 3, reset=0, desc="Put the Z-axis accelerometer into standby"),
                bits("STBY_XG", 2, reset=0, desc="Put the X-axis gyro into standby"),
                bits("STBY_YG", 1, reset=0, desc="Put the Y-axis gyro into standby"),
                bits("STBY_ZG", 0, reset=0, desc="Put the Z-axis gyro into standby"),
            ],
        ),
        reg(
            "WHO_AM_I",
            0x75,
            access=Access.RO,
            reset=0x68,
            desc="Device identity. Contains the upper six bits of the I2C address; reads 0x68.",
        ),
    ]

    registers += data_regs(
        [
            ("ACCEL_XOUT_H", 0x3B, None, "Accelerometer X-axis measurement, high byte"),
            ("ACCEL_XOUT_L", 0x3C, None, "Accelerometer X-axis measurement, low byte"),
            ("ACCEL_YOUT_H", 0x3D, None, "Accelerometer Y-axis measurement, high byte"),
            ("ACCEL_YOUT_L", 0x3E, None, "Accelerometer Y-axis measurement, low byte"),
            ("ACCEL_ZOUT_H", 0x3F, None, "Accelerometer Z-axis measurement, high byte"),
            ("ACCEL_ZOUT_L", 0x40, None, "Accelerometer Z-axis measurement, low byte"),
            ("TEMP_OUT_H", 0x41, None, "Temperature measurement, high byte"),
            ("TEMP_OUT_L", 0x42, None, "Temperature measurement, low byte"),
            ("GYRO_XOUT_H", 0x43, None, "Gyroscope X-axis measurement, high byte"),
            ("GYRO_XOUT_L", 0x44, None, "Gyroscope X-axis measurement, low byte"),
            ("GYRO_YOUT_H", 0x45, None, "Gyroscope Y-axis measurement, high byte"),
            ("GYRO_YOUT_L", 0x46, None, "Gyroscope Y-axis measurement, low byte"),
            ("GYRO_ZOUT_H", 0x47, None, "Gyroscope Z-axis measurement, high byte"),
            ("GYRO_ZOUT_L", 0x48, None, "Gyroscope Z-axis measurement, low byte"),
        ]
    )

    return make_record(
        part_number="MPU6050",
        manufacturer="InvenSense",
        description="Six-axis MEMS gyroscope and accelerometer with I2C",
        buses=[Bus.I2C],
        i2c_addresses=[0x68, 0x69],  # AD0 low / high
        registers=registers,
        source="InvenSense MPU-6000/MPU-6050 Register Map and Descriptions",
    )
