"""Canonical register-map schema.

This module is the contract for everything RegForge does. The extractor fills
it, the validator checks it, the code generators read it, and the corpus stores
it. Changing a field here is a breaking change for every consumer.

Design rule for the LLM-facing models (`Device` and everything it contains):
no field may declare a default. Claude's structured outputs require every
property to appear in `required`, and Pydantic only marks a field required when
it has no default. Optionality is expressed as `T | None` instead, which maps to
a nullable-but-required property.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class Access(str, Enum):
    """Access semantics for a register or bitfield."""

    RW = "rw"
    RO = "ro"
    WO = "wo"
    RW1C = "rw1c"  # write 1 to clear
    RW1S = "rw1s"  # write 1 to set
    W1P = "w1p"  # write 1 to pulse / trigger
    RESERVED = "reserved"
    UNKNOWN = "unknown"


class Bus(str, Enum):
    I2C = "i2c"
    SPI = "spi"
    UART = "uart"
    PARALLEL = "parallel"
    INTERNAL = "internal"  # memory-mapped peripheral inside an MCU
    UNKNOWN = "unknown"


class EnumValue(BaseModel):
    """A named, documented value a bitfield can take."""

    name: str = Field(description="Symbolic name, e.g. 'ODR_100_HZ'. UPPER_SNAKE_CASE.")
    value: int = Field(description="Numeric value of the field when this option is selected.")
    description: str | None = Field(description="What this setting does, or null.")


class BitField(BaseModel):
    """A named run of bits inside a register."""

    name: str = Field(description="Field name exactly as the datasheet spells it, UPPER_SNAKE_CASE.")
    bit_offset: int = Field(description="Zero-based position of the field's least-significant bit.")
    bit_width: int = Field(description="Number of bits the field spans. At least 1.")
    access: Access = Field(description="Access semantics for this field.")
    reset_value: int | None = Field(description="Value after reset, or null if the datasheet does not state one.")
    description: str | None = Field(description="One-line description, or null.")
    enum_values: list[EnumValue] = Field(
        description="Documented discrete settings. Empty list when the field is a plain number."
    )

    @property
    def mask(self) -> int:
        return ((1 << self.bit_width) - 1) << self.bit_offset

    @property
    def bit_high(self) -> int:
        """Inclusive index of the field's most-significant bit."""
        return self.bit_offset + self.bit_width - 1


class Register(BaseModel):
    """A single addressable register."""

    name: str = Field(description="Register name exactly as the datasheet spells it, UPPER_SNAKE_CASE.")
    address: int = Field(description="Register address as an integer.")
    size_bits: int = Field(description="Register width in bits, typically 8, 16 or 32.")
    access: Access = Field(description="Overall access semantics for the register.")
    reset_value: int | None = Field(description="Whole-register reset value, or null if not stated.")
    description: str | None = Field(description="One-line description, or null.")
    fields: list[BitField] = Field(
        description="Bitfields within this register. Empty list when the datasheet treats it as one opaque value."
    )


class Provenance(BaseModel):
    """Where a register map came from and how much it should be trusted.

    Not part of the LLM-facing extraction schema - RegForge fills this in.
    """

    source_sha256: str | None = None
    source_filename: str | None = None
    source_pages: list[int] = Field(default_factory=list)
    extraction_model: str | None = None
    extracted_at: str | None = None
    regforge_version: str | None = None
    schema_version: str = SCHEMA_VERSION
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    verified: bool = False
    verified_by: str | None = None
    notes: str | None = None


class Device(BaseModel):
    """A chip and its complete register map. The unit of value in the corpus."""

    part_number: str = Field(description="Canonical part number, e.g. 'BME280'. No vendor prefix, no packaging suffix.")
    manufacturer: str = Field(description="Manufacturer name, e.g. 'Bosch Sensortec'.")
    description: str | None = Field(description="One-line description of what the chip is.")
    buses: list[Bus] = Field(description="Every control bus the chip's registers can be reached over.")
    i2c_addresses: list[int] = Field(
        description="Possible 7-bit I2C addresses as integers. Empty list if the part is not an I2C device."
    )
    register_address_bits: int = Field(description="Width of a register address in bits, typically 8 or 16.")
    registers: list[Register] = Field(description="Every register documented in the supplied pages.")


class DeviceRecord(BaseModel):
    """What actually gets written to the corpus: a device plus its provenance."""

    device: Device
    provenance: Provenance = Field(default_factory=Provenance)
