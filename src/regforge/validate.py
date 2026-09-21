"""Deterministic validation of an extracted register map.

Everything in here is pure Python: no model calls, no cost, no nondeterminism.
That matters more than it sounds. A language model reading a datasheet table
will occasionally slip a bit offset, overlap two fields, or invent a reset value
that does not fit its register. Those mistakes are individually plausible and
collectively fatal for generated driver code -- and almost all of them are
mechanically detectable.

This module is what lets RegForge label a map "verified" and mean something.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .models import Device, Register

C_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LEADING_DIGIT_RE = re.compile(r"^[0-9][A-Za-z0-9_]*$")

# Words that must never become a bare C identifier in generated headers.
C_RESERVED = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned",
    "void", "volatile", "while", "bool", "true", "false",
}


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str
    where: str

    def __str__(self) -> str:
        return f"[{self.severity.value:7}] {self.code:22} {self.where}: {self.message}"


def _fits(value: int, width_bits: int) -> bool:
    return 0 <= value < (1 << width_bits)


def _check_identifier(name: str, where: str, findings: list[Finding]) -> None:
    if not name or not name.strip():
        findings.append(Finding(Severity.ERROR, "EMPTY_NAME", "name is empty", where))
        return
    if not C_IDENT_RE.match(name):
        # A leading digit is routine in datasheet enum names ("0_5_MS", "2X_GAIN")
        # and codegen handles it losslessly, so it is a note rather than a warning.
        # Anything else means characters are actually being rewritten.
        benign = LEADING_DIGIT_RE.match(name) is not None
        findings.append(
            Finding(
                Severity.INFO if benign else Severity.WARNING,
                "LEADING_DIGIT" if benign else "NON_C_IDENTIFIER",
                f"{name!r} starts with a digit; codegen will prefix it with 'N'"
                if benign
                else f"{name!r} is not a valid C identifier; codegen will sanitise it",
                where,
            )
        )
    if name.lower() in C_RESERVED:
        findings.append(
            Finding(Severity.WARNING, "C_RESERVED_WORD", f"{name!r} collides with a C keyword", where)
        )


def _validate_register(reg: Register, addr_bits: int, findings: list[Finding]) -> None:
    where = f"register {reg.name}"
    _check_identifier(reg.name, where, findings)

    if reg.size_bits <= 0:
        findings.append(
            Finding(Severity.ERROR, "BAD_REGISTER_WIDTH", f"size_bits={reg.size_bits} must be positive", where)
        )
        return
    if reg.size_bits % 8 != 0:
        findings.append(
            Finding(Severity.WARNING, "ODD_REGISTER_WIDTH", f"size_bits={reg.size_bits} is not a multiple of 8", where)
        )

    if reg.address < 0:
        findings.append(Finding(Severity.ERROR, "NEGATIVE_ADDRESS", f"address={reg.address}", where))
    elif addr_bits > 0 and not _fits(reg.address, addr_bits):
        findings.append(
            Finding(
                Severity.ERROR,
                "ADDRESS_OUT_OF_RANGE",
                f"address 0x{reg.address:X} does not fit in {addr_bits} address bits",
                where,
            )
        )

    if reg.reset_value is not None and not _fits(reg.reset_value, reg.size_bits):
        findings.append(
            Finding(
                Severity.ERROR,
                "RESET_TOO_WIDE",
                f"reset_value 0x{reg.reset_value:X} does not fit in {reg.size_bits} bits",
                where,
            )
        )

    if not reg.fields:
        findings.append(Finding(Severity.INFO, "NO_FIELDS", "register has no documented bitfields", where))

    # Bit-level occupancy map: catches overlap and overrun in one pass.
    occupancy: dict[int, str] = {}
    seen_field_names: set[str] = set()

    for f in reg.fields:
        fwhere = f"{reg.name}.{f.name}"
        _check_identifier(f.name, fwhere, findings)

        if f.name in seen_field_names:
            findings.append(Finding(Severity.ERROR, "DUPLICATE_FIELD", f"field {f.name!r} declared twice", where))
        seen_field_names.add(f.name)

        if f.bit_width < 1:
            findings.append(
                Finding(Severity.ERROR, "BAD_FIELD_WIDTH", f"bit_width={f.bit_width} must be >= 1", fwhere)
            )
            continue
        if f.bit_offset < 0:
            findings.append(
                Finding(Severity.ERROR, "BAD_FIELD_OFFSET", f"bit_offset={f.bit_offset} is negative", fwhere)
            )
            continue
        if f.bit_high >= reg.size_bits:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "FIELD_OVERRUNS_REGISTER",
                    f"occupies bits [{f.bit_high}:{f.bit_offset}] but the register is only {reg.size_bits} bits wide",
                    fwhere,
                )
            )
            continue

        for bit in range(f.bit_offset, f.bit_high + 1):
            if bit in occupancy and occupancy[bit] != f.name:
                findings.append(
                    Finding(
                        Severity.ERROR,
                        "FIELD_OVERLAP",
                        f"bit {bit} claimed by both {occupancy[bit]!r} and {f.name!r}",
                        where,
                    )
                )
                break
            occupancy[bit] = f.name

        if f.reset_value is not None and not _fits(f.reset_value, f.bit_width):
            findings.append(
                Finding(
                    Severity.ERROR,
                    "FIELD_RESET_TOO_WIDE",
                    f"reset_value 0x{f.reset_value:X} does not fit in {f.bit_width} bits",
                    fwhere,
                )
            )

        seen_enum_names: set[str] = set()
        seen_enum_values: set[int] = set()
        for ev in f.enum_values:
            _check_identifier(ev.name, f"{fwhere}.{ev.name}", findings)
            if not _fits(ev.value, f.bit_width):
                findings.append(
                    Finding(
                        Severity.ERROR,
                        "ENUM_TOO_WIDE",
                        f"{ev.name}=0x{ev.value:X} does not fit in {f.bit_width} bits",
                        fwhere,
                    )
                )
            if ev.name in seen_enum_names:
                findings.append(Finding(Severity.ERROR, "DUPLICATE_ENUM_NAME", f"{ev.name!r} declared twice", fwhere))
            if ev.value in seen_enum_values:
                findings.append(
                    Finding(Severity.WARNING, "DUPLICATE_ENUM_VALUE", f"value 0x{ev.value:X} used twice", fwhere)
                )
            seen_enum_names.add(ev.name)
            seen_enum_values.add(ev.value)

    # Cross-check: do the field reset values agree with the register reset value?
    if reg.reset_value is not None and reg.fields:
        known = [f for f in reg.fields if f.reset_value is not None and f.bit_high < reg.size_bits]
        if known:
            composed = 0
            covered_mask = 0
            for f in known:
                composed |= (f.reset_value & ((1 << f.bit_width) - 1)) << f.bit_offset
                covered_mask |= f.mask
            if (reg.reset_value & covered_mask) != composed:
                findings.append(
                    Finding(
                        Severity.WARNING,
                        "RESET_MISMATCH",
                        f"register reset 0x{reg.reset_value:X} disagrees with composed field resets "
                        f"0x{composed:X} over mask 0x{covered_mask:X}",
                        where,
                    )
                )

    # Undocumented bits are normal in real datasheets, but worth surfacing.
    if reg.fields:
        undocumented = reg.size_bits - len(occupancy)
        if undocumented > 0:
            findings.append(
                Finding(
                    Severity.INFO,
                    "UNDOCUMENTED_BITS",
                    f"{undocumented} of {reg.size_bits} bits have no named field",
                    where,
                )
            )


def validate_device(device: Device) -> list[Finding]:
    """Run every structural check. Returns findings ordered error-first."""
    findings: list[Finding] = []
    where = f"device {device.part_number}"

    if not device.part_number.strip():
        findings.append(Finding(Severity.ERROR, "NO_PART_NUMBER", "part_number is empty", where))

    if not device.registers:
        findings.append(Finding(Severity.ERROR, "NO_REGISTERS", "no registers were extracted", where))

    if device.register_address_bits <= 0:
        findings.append(
            Finding(
                Severity.ERROR,
                "BAD_ADDRESS_WIDTH",
                f"register_address_bits={device.register_address_bits} must be positive",
                where,
            )
        )

    for addr in device.i2c_addresses:
        if not 0 <= addr <= 0x7F:
            findings.append(
                Finding(
                    Severity.WARNING,
                    "BAD_I2C_ADDRESS",
                    f"0x{addr:X} is not a 7-bit address; it may have been captured in 8-bit form",
                    where,
                )
            )

    seen_names: set[str] = set()
    seen_addrs: dict[int, str] = {}
    for reg in device.registers:
        if reg.name in seen_names:
            findings.append(Finding(Severity.ERROR, "DUPLICATE_REGISTER", f"{reg.name!r} declared twice", where))
        seen_names.add(reg.name)

        if reg.address in seen_addrs and seen_addrs[reg.address] != reg.name:
            # Legitimate in banked or read/write-split maps, so this is a warning.
            findings.append(
                Finding(
                    Severity.WARNING,
                    "DUPLICATE_ADDRESS",
                    f"address 0x{reg.address:X} shared by {seen_addrs[reg.address]!r} and {reg.name!r}",
                    where,
                )
            )
        else:
            seen_addrs[reg.address] = reg.name

        _validate_register(reg, device.register_address_bits, findings)

    order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return sorted(findings, key=lambda f: (order[f.severity], f.where, f.code))


def summarise(findings: list[Finding]) -> dict[str, int]:
    return {
        "errors": sum(1 for f in findings if f.severity is Severity.ERROR),
        "warnings": sum(1 for f in findings if f.severity is Severity.WARNING),
        "info": sum(1 for f in findings if f.severity is Severity.INFO),
    }


def is_clean(findings: list[Finding]) -> bool:
    """True when nothing found would produce incorrect driver code."""
    return not any(f.severity is Severity.ERROR for f in findings)


def coverage_score(device: Device) -> float:
    """Fraction of bits named, across registers that document any bitfields.

    A proxy for "when the extractor found fields, did it find all of them".
    Registers the datasheet treats as one opaque value -- ADC output bytes, FIFO
    data -- are excluded rather than counted as misses, because a driver has
    nothing to name in them and counting them would make a complete extraction
    of a data-heavy part look like a bad one.

    Read it alongside the NO_FIELDS notes, which is where a genuinely missed
    register map shows up.
    """
    total = 0
    named = 0
    for reg in device.registers:
        if reg.size_bits <= 0 or not reg.fields:
            continue
        total += reg.size_bits
        bits: set[int] = set()
        for f in reg.fields:
            if f.bit_width >= 1 and f.bit_offset >= 0 and f.bit_high < reg.size_bits:
                bits.update(range(f.bit_offset, f.bit_high + 1))
        named += len(bits)
    return (named / total) if total else 0.0


__all__ = [
    "Finding",
    "Severity",
    "validate_device",
    "summarise",
    "is_clean",
    "coverage_score",
]
