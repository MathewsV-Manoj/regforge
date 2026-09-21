"""Shared constructors for hand-authored seed maps.

Every seed in this package is transcribed by hand and ships **unverified**. The
same rule the extractor is given applies here: transcribe, do not infer. Where a
datasheet does not state a reset value, the seed says `None` rather than a
plausible-looking number. A null is correct; a guess is a defect that survives
into somebody's driver.
"""

from __future__ import annotations

from regforge import __version__
from regforge.models import (
    Access,
    BitField,
    Bus,
    Device,
    DeviceRecord,
    EnumValue,
    Provenance,
    Register,
)

__all__ = [
    "Access",
    "Bus",
    "EnumValue",
    "bits",
    "data_regs",
    "make_record",
    "reg",
]


def bits(
    name: str,
    offset: int,
    width: int = 1,
    *,
    access: Access = Access.RW,
    reset: int | None = None,
    desc: str | None = None,
    enums: list[EnumValue] | None = None,
) -> BitField:
    return BitField(
        name=name,
        bit_offset=offset,
        bit_width=width,
        access=access,
        reset_value=reset,
        description=desc,
        enum_values=enums or [],
    )


def reg(
    name: str,
    address: int,
    *,
    size: int = 8,
    access: Access = Access.RW,
    reset: int | None = None,
    desc: str | None = None,
    fields: list[BitField] | None = None,
) -> Register:
    return Register(
        name=name,
        address=address,
        size_bits=size,
        access=access,
        reset_value=reset,
        description=desc,
        fields=fields or [],
    )


def data_regs(spec: list[tuple[str, int, int | None, str]], *, size: int = 8) -> list[Register]:
    """Build a run of opaque read-only data registers.

    Measurement output is genuinely field-less in most datasheets, so these
    carry no bitfields on purpose rather than through incomplete transcription.
    """
    return [
        reg(name, addr, size=size, access=Access.RO, reset=reset, desc=desc)
        for name, addr, reset, desc in spec
    ]


def make_record(
    *,
    part_number: str,
    manufacturer: str,
    description: str,
    buses: list[Bus],
    i2c_addresses: list[int],
    registers: list[Register],
    source: str,
    address_bits: int = 8,
    notes: str | None = None,
) -> DeviceRecord:
    device = Device(
        part_number=part_number,
        manufacturer=manufacturer,
        description=description,
        buses=buses,
        i2c_addresses=i2c_addresses,
        register_address_bits=address_bits,
        registers=sorted(registers, key=lambda r: r.address),
    )
    provenance = Provenance(
        source_filename=f"{source} (hand-transcribed)",
        source_pages=[],
        extraction_model=None,
        regforge_version=__version__,
        verified=False,
        notes=(
            notes
            or (
                f"Hand-authored seed entry, not machine-extracted. Check against {source} "
                f"before trusting it, then mark it verified."
            )
        ),
    )
    return DeviceRecord(device=device, provenance=provenance)
