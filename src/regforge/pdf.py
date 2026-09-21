"""PDF loading, register-map page detection, and page slicing.

The single biggest cost lever in RegForge lives here. A 200-page datasheet is
roughly 150K tokens; the register map inside it is usually 8 to 25 pages. Paying
to send the whole document on every extraction would make the unit economics
roughly ten times worse for no accuracy gain, so we locate the register section
first with free local heuristics and send only that slice.

We send the slice as PDF rather than extracted text on purpose. Register maps
are tables, and text extraction routinely scrambles column order -- which is
exactly the information a bit offset depends on. Letting the model see the page
layout is worth the extra tokens.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter

# Signals that a page is part of a register map table, with weights tuned on
# the seed corpus. None of these is decisive alone; the sum is.
_HEX_ADDR = re.compile(r"\b0x[0-9A-Fa-f]{1,4}\b")
_BIT_RANGE = re.compile(r"[\[<]\s*\d{1,2}\s*:\s*\d{1,2}\s*[\]>]")
_BIT_LABEL = re.compile(r"\bbits?\s*\d{1,2}\b", re.IGNORECASE)
_ACCESS_TOK = re.compile(r"\b(R/W|RW|R/O|RO|W/O|WO|RW1C|W1C)\b")
_RESET_TOK = re.compile(r"\b(reset|default|por)\s*(value|state)?\b", re.IGNORECASE)
_REG_WORD = re.compile(r"\bregisters?\b", re.IGNORECASE)
_RESERVED = re.compile(r"\breserved\b", re.IGNORECASE)


@dataclass
class PageScore:
    index: int  # zero-based
    score: float
    hex_addrs: int
    bit_ranges: int


@dataclass
class LoadedPdf:
    path: str
    filename: str
    sha256: str
    page_texts: list[str]

    @property
    def page_count(self) -> int:
        return len(self.page_texts)


def load_pdf(path: str) -> LoadedPdf:
    """Read a PDF and extract per-page text. Text is used only for scoring."""
    with open(path, "rb") as fh:
        raw = fh.read()

    digest = hashlib.sha256(raw).hexdigest()
    reader = PdfReader(io.BytesIO(raw))

    if reader.is_encrypted:
        # Many vendor datasheets ship with an empty owner password.
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover - depends on the file
            raise ValueError(f"{path} is encrypted and could not be opened") from exc

    texts: list[str] = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            # A page that will not extract is still a page; keep the indices aligned.
            texts.append("")

    import os

    return LoadedPdf(path=path, filename=os.path.basename(path), sha256=digest, page_texts=texts)


def score_page(text: str) -> PageScore:
    """Heuristic likelihood that a page contains register-map tables."""
    if not text.strip():
        return PageScore(-1, 0.0, 0, 0)

    hex_addrs = len(_HEX_ADDR.findall(text))
    bit_ranges = len(_BIT_RANGE.findall(text))
    bit_labels = len(_BIT_LABEL.findall(text))
    access_toks = len(_ACCESS_TOK.findall(text))
    reset_toks = len(_RESET_TOK.findall(text))
    reg_words = len(_REG_WORD.findall(text))
    reserved = len(_RESERVED.findall(text))

    # Saturating contributions: ten hex addresses is a strong signal, a hundred
    # is not ten times stronger, and an address table in an ordering guide
    # should not outrank a real register page.
    score = (
        3.0 * min(hex_addrs, 12) / 12
        + 3.0 * min(bit_ranges, 8) / 8
        + 2.0 * min(bit_labels, 8) / 8
        + 2.5 * min(access_toks, 8) / 8
        + 1.5 * min(reset_toks, 4) / 4
        + 1.5 * min(reg_words, 6) / 6
        + 1.0 * min(reserved, 6) / 6
    )
    return PageScore(-1, score, hex_addrs, bit_ranges)


def find_register_pages(
    pdf: LoadedPdf,
    *,
    threshold: float = 4.0,
    context: int = 1,
    max_pages: int = 40,
) -> list[int]:
    """Return zero-based page indices likely to hold the register map.

    `context` pads each hit so a table that spills onto a quiet continuation
    page is not truncated mid-register.
    """
    scores: list[PageScore] = []
    for i, text in enumerate(pdf.page_texts):
        ps = score_page(text)
        scores.append(PageScore(i, ps.score, ps.hex_addrs, ps.bit_ranges))

    hits = {s.index for s in scores if s.score >= threshold}

    if not hits:
        # Nothing cleared the bar. Fall back to the best-scoring pages so the
        # caller still gets a usable slice instead of an empty one.
        ranked = sorted(scores, key=lambda s: s.score, reverse=True)
        hits = {s.index for s in ranked[:max_pages] if s.score > 0}

    padded: set[int] = set()
    for i in hits:
        for j in range(max(0, i - context), min(pdf.page_count, i + context + 1)):
            padded.add(j)

    selected = sorted(padded)

    if len(selected) > max_pages:
        # Keep the highest-scoring pages, then restore document order so the
        # model reads the map the way the datasheet lays it out.
        by_score = {s.index: s.score for s in scores}
        selected = sorted(sorted(selected, key=lambda i: by_score[i], reverse=True)[:max_pages])

    return selected


def slice_pdf(path: str, page_indices: list[int]) -> bytes:
    """Build a new in-memory PDF containing only the given zero-based pages."""
    if not page_indices:
        raise ValueError("no pages selected")

    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"{path} is encrypted and could not be opened") from exc

    writer = PdfWriter()
    for i in page_indices:
        if 0 <= i < len(reader.pages):
            writer.add_page(reader.pages[i])

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def chunk_pages(page_indices: list[int], chunk_size: int = 12) -> list[list[int]]:
    """Split a page selection into contiguous chunks for separate extraction passes.

    Large register maps exceed what one pass handles reliably. Chunking keeps
    each request focused and lets partial failures be retried in isolation.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [page_indices[i : i + chunk_size] for i in range(0, len(page_indices), chunk_size)]


__all__ = [
    "LoadedPdf",
    "PageScore",
    "load_pdf",
    "score_page",
    "find_register_pages",
    "slice_pdf",
    "chunk_pages",
]
