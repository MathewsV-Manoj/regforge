"""Code generators. Shared identifier handling lives here."""

from __future__ import annotations

import re

_NON_IDENT = re.compile(r"[^A-Za-z0-9]+")

_C_RESERVED = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned",
    "void", "volatile", "while",
}


def c_ident(text: str, *, upper: bool = True) -> str:
    """Turn a datasheet name into a safe C identifier fragment.

    Datasheets are full of names like `CTRL_MEAS[1:0]`, `t_sb`, `2X_GAIN` and
    `RESERVED`. All of them have to survive into compilable C without colliding
    or starting with a digit.
    """
    s = _NON_IDENT.sub("_", (text or "").strip()).strip("_")
    s = re.sub(r"_{2,}", "_", s)
    if not s:
        s = "UNNAMED"
    if s[0].isdigit():
        # Prefix with a letter rather than an underscore. Datasheet enum names
        # like "0_5_MS" are common, and "_0_5_MS" would concatenate into a
        # double underscore, which is reserved in C++ and ill-advised in C.
        s = "N" + s
    s = s.upper() if upper else s.lower()
    if not upper and s in _C_RESERVED:
        s = s + "_"
    return s


class NameAllocator:
    """Hands out unique identifiers, because two datasheet names can sanitise
    to the same token and a duplicate #define is a compile error."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def take(self, name: str) -> str:
        candidate = name
        n = 2
        while candidate in self._seen:
            candidate = f"{name}_{n}"
            n += 1
        self._seen.add(candidate)
        return candidate


def stdint_type(size_bits: int) -> str:
    for width in (8, 16, 32, 64):
        if size_bits <= width:
            return f"uint{width}_t"
    return "uint64_t"


def hex_literal(value: int, size_bits: int = 8) -> str:
    digits = max(2, ((size_bits + 3) // 4))
    return f"0x{value:0{digits}X}u"


__all__ = ["c_ident", "NameAllocator", "stdint_type", "hex_literal"]
