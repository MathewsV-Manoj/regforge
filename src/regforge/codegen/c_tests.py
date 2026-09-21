"""Generate `<part>_regs_test.c`: compile-time proof that the generated bit math is correct.

The failure mode this exists for is specific. A generated header always
compiles -- it is just `#define`s -- so "it builds" tells you nothing about
whether `OSRS_T_SET` actually writes bits 7:5. You find out on a logic analyser,
at which point you have lost an afternoon.

So RegForge emits assertions derived from the same register map, checked by the
compiler, with no target hardware and no test runner:

    riscv32-esp-elf-gcc -std=c99 -Wall -Wextra -Werror -c bme280_regs_test.c

A failure here is a compile error naming the exact field. The assertions use the
negative-array-size idiom rather than `_Static_assert` so they work on C99
toolchains, which is most embedded toolchains.
"""

from __future__ import annotations

from ..models import DeviceRecord
from . import NameAllocator, c_ident

_PREAMBLE = """\
/* Portable compile-time assertion: C99-safe, no _Static_assert required. */
#ifndef REGFORGE_STATIC_ASSERT
#define REGFORGE_STATIC_ASSERT(cond, tag) \\
    typedef char regforge_assert_##tag[(cond) ? 1 : -1]
#endif
"""


class _Asserter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.alloc = NameAllocator()
        self.count = 0

    def add(self, expr: str, tag: str, comment: str | None = None) -> None:
        tag = self.alloc.take(c_ident(tag, upper=False))
        if comment:
            self.lines.append(f"/* {comment} */")
        self.lines.append(f"REGFORGE_STATIC_ASSERT({expr}, {tag});")
        self.count += 1

    def blank(self) -> None:
        self.lines.append("")


def generate_regs_test(record: DeviceRecord) -> str:
    d = record.device
    prefix = c_ident(d.part_number)
    lower = c_ident(d.part_number, upper=False)
    a = _Asserter()

    for reg in d.registers:
        rname = f"{prefix}_{c_ident(reg.name)}"
        a.blank()
        a.lines.append(f"/* ---- {reg.name} @ 0x{reg.address:X} ---- */")

        # The address must be representable in the device's address width.
        if d.register_address_bits > 0:
            a.add(
                f"({rname}) <= 0x{(1 << d.register_address_bits) - 1:X}u",
                f"{rname}_addr_fits",
                f"address fits in {d.register_address_bits} address bits",
            )

        if reg.reset_value is not None:
            a.add(
                f"({rname}_RESET) <= 0x{(1 << reg.size_bits) - 1:X}u",
                f"{rname}_reset_fits",
            )

        for f in reg.fields:
            if f.bit_width < 1 or f.bit_offset < 0 or f.bit_high >= reg.size_bits:
                continue

            fname = f"{rname}_{c_ident(f.name)}"
            expected_mask = f.mask
            max_val = (1 << f.bit_width) - 1
            reg_max = (1 << reg.size_bits) - 1

            # 1. The mask really is width bits, positioned at shift.
            a.add(
                f"({fname}_MASK) == (((1u << {fname}_WIDTH) - 1u) << {fname}_SHIFT)",
                f"{fname}_mask_shape",
                f"{f.name} occupies bits [{f.bit_high}:{f.bit_offset}]",
            )
            a.add(f"({fname}_MASK) == 0x{expected_mask:X}u", f"{fname}_mask_value")
            a.add(f"({fname}_SHIFT) == {f.bit_offset}u", f"{fname}_shift_value")
            a.add(f"({fname}_WIDTH) == {f.bit_width}u", f"{fname}_width_value")

            # 2. The field does not leave its register.
            a.add(
                f"(({fname}_MASK) & ~0x{reg_max:X}u) == 0u",
                f"{fname}_within_register",
            )

            # 3. GET extracts from the right place: a register holding only this
            #    field at max should read back as max.
            a.add(
                f"{fname}_GET(0x{expected_mask:X}u) == 0x{max_val:X}u",
                f"{fname}_get_extracts",
            )
            a.add(f"{fname}_GET(0u) == 0u", f"{fname}_get_zero")

            # 4. SET places the value at the right offset.
            a.add(
                f"{fname}_SET(0u, 0x{max_val:X}u) == 0x{expected_mask:X}u",
                f"{fname}_set_places",
            )

            # 5. SET leaves every other bit alone -- the read-modify-write
            #    property that makes or breaks a driver.
            a.add(
                f"{fname}_SET(0x{reg_max:X}u, 0u) == 0x{reg_max & ~expected_mask:X}u",
                f"{fname}_set_preserves",
            )

            # 6. SET then GET round-trips.
            a.add(
                f"{fname}_GET({fname}_SET(0u, 0x{max_val:X}u)) == 0x{max_val:X}u",
                f"{fname}_roundtrip",
            )

            # 7. An over-wide value cannot corrupt neighbouring fields.
            a.add(
                f"({fname}_SET(0u, 0xFFu) & ~({fname}_MASK)) == 0u",
                f"{fname}_set_clamped",
            )

            if f.reset_value is not None:
                a.add(
                    f"0x{f.reset_value:X}u <= 0x{max_val:X}u",
                    f"{fname}_reset_fits",
                )

            for ev in f.enum_values:
                ename = f"{fname}_{c_ident(ev.name)}"
                a.add(f"({ename}) <= 0x{max_val:X}u", f"{ename}_fits")

    body = "\n".join(a.lines)
    return f"""\
/*
 * {d.part_number} register map -- generated self-check
 * Generated by RegForge {record.provenance.regforge_version or '?'}. DO NOT EDIT BY HAND.
 *
 * Compile this file to verify the generated bit arithmetic. It produces no
 * code and needs no hardware:
 *
 *     gcc -std=c99 -Wall -Wextra -Werror -c {lower}_regs_test.c
 *
 * Every assertion below is derived from the same register map as the header,
 * so a failure means the map and the macros disagree -- which is exactly the
 * bug you cannot see by reading either one.
 *
 * {a.count} assertions.
 */

#include "{lower}_regs.h"

{_PREAMBLE}
{body}

/* Silence "empty translation unit" pedantry on toolchains that warn about it. */
typedef int regforge_{lower}_test_tu;
"""


__all__ = ["generate_regs_test"]
