# Contributing

The most valuable contribution to RegForge is **a part**. The tool is only as
useful as the corpus behind it, and every part added makes it instant and free
for the next person who needs that chip.

Two ways to help, in order of impact.

---

## 1. Verify a part that is already in the corpus

Every shipped map is currently **unverified**: transcribed, validated
mechanically, but never checked against the datasheet by a human. Verifying one
is a genuinely useful half hour and needs no API key.

```bash
regforge gen BME280 --out /tmp/check --tests
```

Open the generated header next to the datasheet's register section and check:

- **Addresses.** Does each `#define <PART>_<REG>` match the datasheet?
- **Bit positions.** For each field, does `_SHIFT` equal the low bit and
  `_WIDTH` the span? `[7:5]` means `SHIFT 5, WIDTH 3`. This is where almost all
  real errors live.
- **Reset values.** Do they match, and does the datasheet actually state one?
  A field with no documented reset should be `null`, not `0`.
- **Enum values.** Are the named settings right, and do any of them collide?
- **Missing registers.** Anything in the datasheet that is not in the map?

Then record it:

```bash
regforge verify BME280 --by "Your Name" --notes "checked against BST-BME280-DS002 rev 1.6"
```

Open a PR with the updated JSON. If you found an error, fix the builder in
`examples/seeds/` and re-run `python examples/seed_corpus.py` so the committed
corpus and the builder stay in step — CI diffs them.

---

## 2. Add a new part

### From a datasheet, with an API key

```bash
regforge scan datasheet.pdf                       # free: check the page picks
regforge extract datasheet.pdf --part ACME1234 --pages 24-31
regforge check ACME1234 --verbose
```

Fix anything the validator flags, verify it by hand as above, then add the JSON
under `corpus/<manufacturer-slug>/<part-slug>.json`.

### By hand, no API key needed

Copy the shape of [`examples/seeds/bme280.py`](examples/seeds/bme280.py), which
is the reference seed, then:

1. Add your module to `SEEDS` in `examples/seeds/__init__.py`.
2. Run `python examples/seed_corpus.py --check` — it validates without writing.
3. Run `python examples/seed_corpus.py` to write the JSON.
4. Run `pytest` and add spot checks to `tests/test_seeds.py` for the facts most
   likely to drift: the chip ID, the bit positions people get backwards, any
   reset value that decomposes into fields.

---

## The one rule that matters

**Transcribe, do not infer.** This is the rule the extractor is given, and it
applies identically to hand-authored maps:

> When the datasheet does not state something, emit `null`. Never fill a gap
> with a plausible value, a value from a similar part, or a value you remember
> from elsewhere. A null is correct; a guess is a defect.

A guessed reset value does not look wrong in review. It looks exactly like a
real one, right up until it silently generates a driver that misconfigures
somebody's hardware. The DS3231 seed is the worked example: its timekeeping
registers carry `reset_value = None` because the datasheet states none, even
though `0x00` would have looked perfectly reasonable.

Related: if two registers share an address (banked or mirrored maps), emit the
primary address once and note the alternate in the description. `MCP23017`'s
`IOCON` shows that pattern.

---

## Development

```bash
git clone https://github.com/<you>/regforge && cd regforge
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
pytest -q
```

Before opening a PR:

```bash
pytest -q                                   # full suite
python examples/seed_corpus.py --check      # every seed validates

# The check that actually matters: a C compiler agrees with the bit math.
regforge gen BME280 --out /tmp/rf --driver --tests
gcc -std=c99 -Wall -Wextra -Wpedantic -Werror -c /tmp/rf/bme280_regs_test.c -o /dev/null
gcc -std=c99 -Wall -Wextra -Wpedantic -Werror -c /tmp/rf/bme280.c -o /dev/null
```

No C compiler handy? CI runs all of it, including a negative test that corrupts
a mask and asserts the generated self-check refuses to compile. **Do not delete
that test.** Without it the assertions could silently become decorative, and the
central claim of this project — that the generated bit math is proved rather
than trusted — would quietly stop being true.

### Where things live

| Path | What it is |
|---|---|
| `src/regforge/models.py` | The schema. Everything depends on it; changes are breaking. |
| `src/regforge/validate.py` | Deterministic checks. Pure Python, no model calls. |
| `src/regforge/pdf.py` | Page scoring and slicing — the cost lever. |
| `src/regforge/extract.py` | The only code that spends money. |
| `src/regforge/codegen/` | Header, driver and self-check generators. |
| `examples/seeds/` | Hand-authored maps, source of truth for `corpus/`. |

### Scope

Good fits: more parts, better page-detection heuristics, new codegen targets
(Rust, Zephyr devicetree, MicroPython), better validation rules.

Out of scope for now: scanned/image-only datasheets, memory-mapped MCU
peripheral maps, and transcribing compensation formulas. See the README's
"What it does not do yet".
