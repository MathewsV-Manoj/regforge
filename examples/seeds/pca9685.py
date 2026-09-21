"""NXP PCA9685 -- 16-channel 12-bit PWM controller, I2C.

The servo-driver board. Two details people trip over and both are in the map:
MODE1 boots with SLEEP set so the oscillator is off, and PRESCALE can only be
written while SLEEP is set.
"""

from __future__ import annotations

from ._helpers import Access, Bus, EnumValue, bits, make_record, reg


def _channel_regs():
    """LED0..LED15, four registers each from 0x06."""
    out = []
    for ch in range(16):
        base = 0x06 + 4 * ch
        out += [
            reg(f"LED{ch}_ON_L", base, reset=0x00,
                desc=f"Channel {ch} turn-on count, bits [7:0]"),
            reg(f"LED{ch}_ON_H", base + 1, reset=0x00,
                desc=f"Channel {ch} turn-on count bits [11:8], plus the full-ON bit",
                fields=[
                    bits("FULL_ON", 4, reset=0, desc="Drive the output permanently high"),
                    bits("ON_COUNT_H", 0, 4, reset=0, desc="Turn-on count, bits [11:8]"),
                ]),
            reg(f"LED{ch}_OFF_L", base + 2, reset=0x00,
                desc=f"Channel {ch} turn-off count, bits [7:0]"),
            reg(f"LED{ch}_OFF_H", base + 3, reset=0x00,
                desc=f"Channel {ch} turn-off count bits [11:8], plus the full-OFF bit",
                fields=[
                    bits("FULL_OFF", 4, reset=0, desc="Drive the output permanently low. Takes priority over FULL_ON."),
                    bits("OFF_COUNT_H", 0, 4, reset=0, desc="Turn-off count, bits [11:8]"),
                ]),
        ]
    return out


def build_record():
    registers = [
        reg(
            "MODE1", 0x00, reset=0x11,
            desc="Mode register 1. Note the reset value: SLEEP is set, so the internal "
                 "oscillator is off and no PWM is produced until you clear it.",
            fields=[
                bits("RESTART", 7, access=Access.RW1C, reset=0,
                     desc="Reads 1 when a restart is required; write 1 to clear"),
                bits("EXTCLK", 6, reset=0, desc="Use an external clock. Sticky until power cycle or SWRST."),
                bits("AI", 5, reset=0, desc="Register auto-increment enable"),
                bits("SLEEP", 4, reset=1, desc="Low-power mode, oscillator off. Set at reset."),
                bits("SUB1", 3, reset=0, desc="Respond to I2C subaddress 1"),
                bits("SUB2", 2, reset=0, desc="Respond to I2C subaddress 2"),
                bits("SUB3", 1, reset=0, desc="Respond to I2C subaddress 3"),
                bits("ALLCALL", 0, reset=1, desc="Respond to the LED All Call address"),
            ],
        ),
        reg(
            "MODE2", 0x01, reset=0x04,
            desc="Mode register 2: output drive and inversion",
            fields=[
                bits("INVRT", 4, reset=0, desc="Invert the output logic state"),
                bits("OCH", 3, reset=0, desc="0 = outputs change on STOP, 1 = on ACK"),
                bits("OUTDRV", 2, reset=1, desc="0 = open drain, 1 = totem pole"),
                bits(
                    "OUTNE", 0, 2, reset=0b00,
                    desc="Output state when OE is high",
                    enums=[
                        EnumValue(name="LOW", value=0b00, description="Outputs go low"),
                        EnumValue(name="OUTDRV_DEPENDENT", value=0b01,
                                  description="High if OUTDRV=1, otherwise high-impedance"),
                        EnumValue(name="HIGH_Z", value=0b10, description="Outputs go high-impedance"),
                    ],
                ),
            ],
        ),
        reg("SUBADR1", 0x02, reset=0xE2, desc="I2C subaddress 1"),
        reg("SUBADR2", 0x03, reset=0xE4, desc="I2C subaddress 2"),
        reg("SUBADR3", 0x04, reset=0xE8, desc="I2C subaddress 3"),
        reg("ALLCALLADR", 0x05, reset=0xE0, desc="LED All Call I2C address"),
    ]

    registers += _channel_regs()

    registers += [
        reg("ALL_LED_ON_L", 0xFA, access=Access.WO, desc="Turn-on count for all channels, bits [7:0]"),
        reg("ALL_LED_ON_H", 0xFB, access=Access.WO, desc="Turn-on count for all channels, bits [11:8] and full-ON",
            fields=[bits("FULL_ON", 4, access=Access.WO, desc="Drive all outputs permanently high")]),
        reg("ALL_LED_OFF_L", 0xFC, access=Access.WO, desc="Turn-off count for all channels, bits [7:0]"),
        reg("ALL_LED_OFF_H", 0xFD, access=Access.WO, desc="Turn-off count for all channels, bits [11:8] and full-OFF",
            fields=[bits("FULL_OFF", 4, access=Access.WO, desc="Drive all outputs permanently low")]),
        reg(
            "PRESCALE", 0xFE, reset=0x1E,
            desc="PWM frequency prescaler. Writable only while MODE1.SLEEP is set. "
                 "prescale = round(osc_clock / (4096 * pwm_freq)) - 1; the 0x1E default is 200 Hz "
                 "with the internal 25 MHz oscillator.",
        ),
        reg("TESTMODE", 0xFF, desc="Factory test mode. Do not write."),
    ]

    return make_record(
        part_number="PCA9685",
        manufacturer="NXP Semiconductors",
        description="16-channel 12-bit PWM LED and servo controller with I2C",
        buses=[Bus.I2C],
        i2c_addresses=list(range(0x40, 0x80)),  # A5:A0 strapping
        registers=registers,
        source="NXP PCA9685 datasheet",
        notes=(
            "Hand-authored seed entry, not machine-extracted. The 64 per-channel LED "
            "registers are generated programmatically from the documented 4-per-channel "
            "layout starting at 0x06. Check against the datasheet before trusting it, then "
            "mark it verified."
        ),
    )
