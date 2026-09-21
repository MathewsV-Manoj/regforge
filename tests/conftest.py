from __future__ import annotations

import pytest

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


def field(name: str, offset: int, width: int, **kw) -> BitField:
    return BitField(
        name=name,
        bit_offset=offset,
        bit_width=width,
        access=kw.get("access", Access.RW),
        reset_value=kw.get("reset_value"),
        description=kw.get("description"),
        enum_values=kw.get("enum_values", []),
    )


def register(name: str, address: int, fields=None, **kw) -> Register:
    return Register(
        name=name,
        address=address,
        size_bits=kw.get("size_bits", 8),
        access=kw.get("access", Access.RW),
        reset_value=kw.get("reset_value"),
        description=kw.get("description"),
        fields=fields or [],
    )


def device(registers, **kw) -> Device:
    return Device(
        part_number=kw.get("part_number", "TESTPART"),
        manufacturer=kw.get("manufacturer", "Acme Semiconductor"),
        description=kw.get("description", "A part that exists only in tests"),
        buses=kw.get("buses", [Bus.I2C]),
        i2c_addresses=kw.get("i2c_addresses", [0x40]),
        register_address_bits=kw.get("register_address_bits", 8),
        registers=registers,
    )


@pytest.fixture
def good_device() -> Device:
    """A small but complete map with no structural problems."""
    return device(
        [
            register(
                "CHIP_ID",
                0x00,
                access=Access.RO,
                reset_value=0x5A,
                description="Identity register",
            ),
            register(
                "CTRL",
                0x01,
                [
                    field(
                        "MODE",
                        0,
                        2,
                        reset_value=0,
                        enum_values=[
                            EnumValue(name="SLEEP", value=0, description="Low power"),
                            EnumValue(name="ACTIVE", value=3, description="Running"),
                        ],
                    ),
                    field("GAIN", 2, 3, reset_value=0),
                    field("ENABLE", 7, 1, reset_value=0),
                ],
                reset_value=0x00,
            ),
        ]
    )


@pytest.fixture
def good_record(good_device) -> DeviceRecord:
    return DeviceRecord(
        device=good_device,
        provenance=Provenance(regforge_version="0.1.0", source_filename="test.pdf", source_pages=[3, 4]),
    )
