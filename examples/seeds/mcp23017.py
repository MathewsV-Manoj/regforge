"""Microchip MCP23017 -- 16-bit I2C I/O expander.

Transcribed for IOCON.BANK = 0, the power-on default, where the A and B port
registers interleave. Setting BANK = 1 remaps the whole address space; that
alternative mapping is not transcribed here, and the description says so rather
than leaving a reader to discover it.

IOCON appears at both 0x0A and 0x0B. Per the extraction rules, the primary
address is emitted once with the alternate noted in the description, instead of
two registers sharing a name.
"""

from __future__ import annotations

from ._helpers import Access, Bus, bits, make_record, reg


def _port_pair(base_name: str, addr_a: int, addr_b: int, *, reset: int | None, desc: str, access=Access.RW):
    return [
        reg(f"{base_name}A", addr_a, access=access, reset=reset, desc=f"{desc} (port A)"),
        reg(f"{base_name}B", addr_b, access=access, reset=reset, desc=f"{desc} (port B)"),
    ]


def build_record():
    registers: list = []

    registers += _port_pair(
        "IODIR", 0x00, 0x01, reset=0xFF,
        desc="Pin direction. 1 = input, 0 = output. All pins are inputs after reset.",
    )
    registers += _port_pair(
        "IPOL", 0x02, 0x03, reset=0x00,
        desc="Input polarity. 1 = the GPIO register reflects the inverted pin value.",
    )
    registers += _port_pair(
        "GPINTEN", 0x04, 0x05, reset=0x00,
        desc="Interrupt-on-change enable, per pin",
    )
    registers += _port_pair(
        "DEFVAL", 0x06, 0x07, reset=0x00,
        desc="Default comparison value, used when INTCON selects comparison mode",
    )
    registers += _port_pair(
        "INTCON", 0x08, 0x09, reset=0x00,
        desc="Interrupt control. 1 = compare against DEFVAL, 0 = compare against the previous value.",
    )

    registers.append(
        reg(
            "IOCON",
            0x0A,
            reset=0x00,
            desc=(
                "Device configuration, shared by both ports. Also readable and writable at 0x0B; "
                "the two addresses are the same physical register."
            ),
            fields=[
                bits(
                    "BANK",
                    7,
                    reset=0,
                    desc=(
                        "Register addressing mode. 0 = A/B registers interleaved (the mapping "
                        "transcribed here), 1 = ports in separate banks."
                    ),
                ),
                bits("MIRROR", 6, reset=0, desc="1 = INTA and INTB are internally connected"),
                bits("SEQOP", 5, reset=0, desc="Sequential operation disable. 1 = the address pointer does not increment."),
                bits("DISSLW", 4, reset=0, desc="Disable slew-rate control on SDA"),
                bits("HAEN", 3, reset=0, desc="Hardware address enable. No effect on the I2C part; present for the SPI variant."),
                bits("ODR", 2, reset=0, desc="1 = INT pin is open drain, overriding INTPOL"),
                bits("INTPOL", 1, reset=0, desc="INT pin polarity when ODR is 0. 0 = active low, 1 = active high."),
            ],
        )
    )

    registers += _port_pair(
        "GPPU", 0x0C, 0x0D, reset=0x00,
        desc="100 kOhm pull-up enable, per pin, on pins configured as inputs",
    )
    registers += _port_pair(
        "INTF", 0x0E, 0x0F, reset=0x00, access=Access.RO,
        desc="Interrupt flags. 1 = this pin caused the interrupt. Read-only.",
    )
    registers += _port_pair(
        "INTCAP", 0x10, 0x11, reset=0x00, access=Access.RO,
        desc="Port value captured at the time of the interrupt. Cleared by reading INTCAP or GPIO.",
    )
    registers += _port_pair(
        "GPIO", 0x12, 0x13, reset=0x00,
        desc="Port value. Reading returns the pin state; writing modifies the output latch.",
    )
    registers += _port_pair(
        "OLAT", 0x14, 0x15, reset=0x00,
        desc="Output latch. Reading returns the latch, not the pin.",
    )

    return make_record(
        part_number="MCP23017",
        manufacturer="Microchip Technology",
        description="16-bit I2C I/O expander with interrupt output",
        buses=[Bus.I2C],
        i2c_addresses=list(range(0x20, 0x28)),  # A2:A0 strapping
        registers=registers,
        source="Microchip MCP23017/MCP23S17 datasheet (DS20001952)",
        notes=(
            "Hand-authored seed entry, not machine-extracted. Transcribed for IOCON.BANK = 0, "
            "the power-on default; the BANK = 1 address map is not covered. Check against the "
            "datasheet before trusting it, then mark it verified."
        ),
    )
