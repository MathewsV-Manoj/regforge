"""Datasheet -> structured register map, via Claude with structured outputs.

Finding the register pages costs nothing: pdf.py scores every page with local
heuristics, so the only model call is the accuracy-critical one. It reads the
sliced pages as PDF rather than extracted text -- text extraction scrambles
table columns, which is exactly the information a bit offset depends on -- and
emits a Device validated against the schema in models.py.

Structured outputs do the schema enforcement, validate.py does the semantic
enforcement, and the combination is what makes the output trustworthy enough to
generate driver code from.

Long maps are extracted in chunks. A chunk boundary can cut a register table in
half, so the same register may come back twice at different levels of detail;
_merge_registers keeps the richer copy.
"""

from __future__ import annotations

import base64
import datetime as _dt
from dataclasses import dataclass, field

import anthropic

from . import __version__
from .costs import DEFAULT_EXTRACT_MODEL, CostLedger, Usage
from .models import Device, DeviceRecord, Provenance, Register
from .pdf import LoadedPdf, chunk_pages, find_register_pages, load_pdf, slice_pdf

EXTRACTION_SYSTEM = """\
You are a precise datasheet register-map extractor. You transcribe register \
tables from semiconductor datasheets into structured data. You are not an \
assistant and you do not explain; you emit data.

Rules, in priority order:

1. TRANSCRIBE, DO NOT INFER. Every value you emit must be readable on the \
supplied pages. When the datasheet does not state something, emit null. Never \
fill a gap with a plausible value, a value from a similar part, or a value you \
remember from elsewhere. A null is correct; a guess is a defect.

2. BIT NUMBERING. `bit_offset` is the zero-based index of the field's \
LEAST-significant bit and `bit_width` is how many bits it spans. A field the \
datasheet writes as [7:4] has bit_offset=4 and bit_width=4. A single bit at \
position 3 has bit_offset=3 and bit_width=1. This is the single most common \
place to make an error -- re-read each row before emitting it.

3. NAMES VERBATIM. Use the register and field names exactly as the datasheet \
spells them, normalised to UPPER_SNAKE_CASE only where the datasheet uses \
spaces or hyphens. Do not expand abbreviations, do not tidy names, do not \
rename for consistency.

4. ADDRESSES AS INTEGERS. `0xF4` becomes 244. If a register is documented at \
more than one address (banked or mirrored), emit the primary address and note \
the alternate in the description.

5. RESERVED BITS COUNT. Include reserved and unnamed-but-documented fields with \
access="reserved". They matter for read-modify-write correctness, so omitting \
them produces broken drivers.

6. SCOPE. Emit only registers documented on the supplied pages. Do not emit a \
register you believe the part has but cannot see. Do not emit pin descriptions, \
electrical characteristics, or command opcodes as registers.

7. ENUMS. Populate enum_values only for fields where the datasheet documents \
discrete named settings. Leave it empty for plain numeric fields such as \
thresholds or counters.
"""

@dataclass
class ExtractionResult:
    record: DeviceRecord
    ledger: CostLedger
    pages_used: list[int]
    truncated_chunks: int = 0
    warnings: list[str] = field(default_factory=list)


def _pdf_block(pdf_bytes: bytes) -> dict:
    """A base64 PDF document content block. Must precede the text block."""
    data = base64.standard_b64encode(pdf_bytes).decode("ascii")
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": data},
    }


def _merge_registers(groups: list[list[Register]]) -> list[Register]:
    """Combine per-chunk register lists.

    Chunk boundaries can cut a table in half, so the same register may appear
    twice with different levels of detail. Keep the richer copy rather than the
    first one seen.
    """
    best: dict[tuple[str, int], Register] = {}
    for group in groups:
        for reg in group:
            key = (reg.name, reg.address)
            existing = best.get(key)
            if existing is None:
                best[key] = reg
                continue
            # Richer = more named fields, then more described fields.
            if len(reg.fields) > len(existing.fields):
                best[key] = reg
            elif len(reg.fields) == len(existing.fields):
                new_desc = sum(1 for f in reg.fields if f.description)
                old_desc = sum(1 for f in existing.fields if f.description)
                if new_desc > old_desc or (reg.description and not existing.description):
                    best[key] = reg

    return sorted(best.values(), key=lambda r: (r.address, r.name))


def _extract_chunk(
    client: anthropic.Anthropic,
    pdf_bytes: bytes,
    *,
    model: str,
    part_hint: str | None,
    max_tokens: int,
) -> tuple[Device | None, Usage, bool]:
    """One extraction pass. Returns (device, usage, was_truncated)."""
    hint = f"\n\nThe part number is {part_hint}." if part_hint else ""
    response = client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": EXTRACTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": [
                    _pdf_block(pdf_bytes),
                    {
                        "type": "text",
                        "text": (
                            "Extract every register documented on these pages into the given "
                            "structure. Follow the numbered rules exactly, especially rule 2 on "
                            "bit numbering." + hint
                        ),
                    },
                ],
            }
        ],
        output_format=Device,
    )

    usage = Usage.from_response(response.usage)
    truncated = getattr(response, "stop_reason", None) == "max_tokens"
    device = getattr(response, "parsed_output", None)
    return device, usage, truncated


def extract_from_pdf(
    path: str,
    *,
    client: anthropic.Anthropic | None = None,
    model: str = DEFAULT_EXTRACT_MODEL,
    part_hint: str | None = None,
    max_pages: int = 40,
    chunk_size: int = 8,
    max_tokens: int = 16000,
    pages: list[int] | None = None,
) -> ExtractionResult:
    """Extract a full register map from a datasheet PDF.

    `pages` overrides automatic detection with an explicit zero-based list,
    which is how you recover when the heuristics pick the wrong section.
    """
    client = client or anthropic.Anthropic()
    ledger = CostLedger()
    warnings: list[str] = []

    pdf: LoadedPdf = load_pdf(path)
    selected = pages if pages is not None else find_register_pages(pdf, max_pages=max_pages)
    if not selected:
        raise ValueError(
            f"no register-map pages found in {pdf.filename}; "
            f"pass --pages to select them manually"
        )

    chunks = chunk_pages(selected, chunk_size=chunk_size)
    groups: list[list[Register]] = []
    head: Device | None = None
    truncated_chunks = 0

    for idx, chunk in enumerate(chunks, start=1):
        pdf_bytes = slice_pdf(path, chunk)
        device, usage, truncated = _extract_chunk(
            client, pdf_bytes, model=model, part_hint=part_hint, max_tokens=max_tokens
        )
        ledger.add(f"chunk{idx}", model, usage)

        if truncated and len(chunk) > 1:
            # Output hit the ceiling: the tail of this chunk is missing. Split
            # it and retry rather than silently returning a partial map.
            warnings.append(f"chunk {idx} hit max_tokens; retrying in halves")
            half = max(1, len(chunk) // 2)
            for sub_idx, sub in enumerate([chunk[:half], chunk[half:]], start=1):
                if not sub:
                    continue
                sub_bytes = slice_pdf(path, sub)
                sub_device, sub_usage, sub_trunc = _extract_chunk(
                    client, sub_bytes, model=model, part_hint=part_hint, max_tokens=max_tokens
                )
                ledger.add(f"chunk{idx}.{sub_idx}", model, sub_usage)
                if sub_trunc:
                    truncated_chunks += 1
                    warnings.append(f"chunk {idx}.{sub_idx} still truncated; map may be incomplete")
                if sub_device is not None:
                    groups.append(sub_device.registers)
                    head = head or sub_device
            continue

        if truncated:
            truncated_chunks += 1
            warnings.append(f"chunk {idx} truncated on a single page; map may be incomplete")

        if device is None:
            warnings.append(f"chunk {idx} returned no parsed output")
            continue

        groups.append(device.registers)
        head = head or device

    if head is None:
        raise RuntimeError("extraction produced no usable output from any chunk")

    merged = Device(
        part_number=(part_hint or head.part_number).strip(),
        manufacturer=head.manufacturer,
        description=head.description,
        buses=head.buses,
        i2c_addresses=head.i2c_addresses,
        register_address_bits=head.register_address_bits,
        registers=_merge_registers(groups),
    )

    total = ledger.total
    provenance = Provenance(
        source_sha256=pdf.sha256,
        source_filename=pdf.filename,
        source_pages=[p + 1 for p in selected],  # store as 1-based, human-facing
        extraction_model=model,
        extracted_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        regforge_version=__version__,
        input_tokens=total.input_tokens + total.cache_read_tokens + total.cache_write_tokens,
        output_tokens=total.output_tokens,
        cost_usd=round(ledger.total_usd, 6),
        verified=False,
    )

    return ExtractionResult(
        record=DeviceRecord(device=merged, provenance=provenance),
        ledger=ledger,
        pages_used=selected,
        truncated_chunks=truncated_chunks,
        warnings=warnings,
    )


__all__ = [
    "ExtractionResult",
    "extract_from_pdf",
    "EXTRACTION_SYSTEM",
    "DEFAULT_EXTRACT_MODEL",
]
