"""Microchip MCP23008 -- 8-bit I2C I/O expander.

The single-port sibling of the MCP23017. Worth seeding separately rather than
telling people to "use half the MCP23017 map": the addresses are completely
different, because with one port there is no A/B interleaving.
"""

from __future__ import annotations

from ._helpers import Access, Bus, bits, make_record, reg


def build_record():
    registers = [
        reg("IODIR", 0x00, reset=0xFF,
            desc="Pin direction. 1 = input, 0 = output. All pins are inputs after reset."),
        reg("IPOL", 0x01, reset=0x00,
            desc="Input polarity. 1 = the GPIO register reflects the inverted pin value."),
        reg("GPINTEN", 0x02, reset=0x00,
            desc="Interrupt-on-change enable, per pin"),
        reg("DEFVAL", 0x03, reset=0x00,
            desc="Default comparison value, used when INTCON selects comparison mode"),
        reg("INTCON", 0x04, reset=0x00,
            desc="Interrupt control. 1 = compare against DEFVAL, 0 = compare against the previous value."),
        reg(
            "IOCON", 0x05, reset=0x00,
            desc="Device configuration. Note there is no BANK bit here -- with a single port "
                 "there is nothing to re-bank.",
            fields=[
                bits("SEQOP", 5, reset=0,
                     desc="Sequential operation disable. 1 = the address pointer does not increment."),
                bits("DISSLW", 4, reset=0, desc="Disable slew-rate control on SDA"),
                bits("HAEN", 3, reset=0,
                     desc="Hardware address enable. No effect on the I2C part; present for the SPI variant."),
                bits("ODR", 2, reset=0, desc="1 = INT pin is open drain, overriding INTPOL"),
                bits("INTPOL", 1, reset=0,
                     desc="INT pin polarity when ODR is 0. 0 = active low, 1 = active high."),
            ],
        ),
        reg("GPPU", 0x06, reset=0x00,
            desc="100 kOhm pull-up enable, per pin, on pins configured as inputs"),
        reg("INTF", 0x07, access=Access.RO, reset=0x00,
            desc="Interrupt flags. 1 = this pin caused the interrupt. Read-only."),
        reg("INTCAP", 0x08, access=Access.RO, reset=0x00,
            desc="Port value captured at the time of the interrupt. Cleared by reading INTCAP or GPIO."),
        reg("GPIO", 0x09, reset=0x00,
            desc="Port value. Reading returns the pin state; writing modifies the output latch."),
        reg("OLAT", 0x0A, reset=0x00,
            desc="Output latch. Reading returns the latch, not the pin."),
    ]

    return make_record(
        part_number="MCP23008",
        manufacturer="Microchip Technology",
        description="8-bit I2C I/O expander with interrupt output",
        buses=[Bus.I2C],
        i2c_addresses=list(range(0x20, 0x28)),  # A2:A0 strapping
        registers=registers,
        source="Microchip MCP23008/MCP23S08 datasheet (DS21919)",
    )
