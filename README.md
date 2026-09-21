# RegForge

[![ci](https://github.com/MathewsV-Manoj/regforge/actions/workflows/ci.yml/badge.svg)](https://github.com/MathewsV-Manoj/regforge/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**[Browse the register maps →](https://mathewsv-manoj.github.io/regforge/)**  ·  7 parts, 100 registers, free to read

**Turn a datasheet into a verified register map and driver code.**

You know the afternoon. A new sensor lands on your desk, the datasheet is 180
pages, and somewhere around page 40 there are twelve register tables you now
have to retype into a header file — getting every bit offset right, because
`[7:5]` means shift 5 and width 3 and getting that backwards costs you a day on
a logic analyser.

RegForge reads those pages, extracts the register map into structured data,
checks it mechanically, and generates the header and driver skeleton.

```bash
regforge extract bst-bme280-ds002.pdf --part BME280 --out ./src --driver
```

```
extracted from pages 24-31
  chunk1     claude-sonnet-5    in= 41,203 out= 5,118 cached=      0  $0.1336
  TOTAL                                                              $0.1336

BME280 (Bosch Sensortec)
  registers: 14   bit coverage: 62%

  0 error(s), 0 warning(s), 21 note(s)   (use --verbose to see notes)
  status: PASS

saved -> corpus/bosch-sensortec/bme280.json
generated:
  src/bme280_regs.h
  src/bme280.h
  src/bme280.c
```

Bit coverage counts only registers that document bitfields, so the BME280's
eight opaque ADC output registers do not drag a complete extraction down to
18%. The `NO_FIELDS` notes are where a genuinely missed register map shows up.

---

## Why this is not just "ask an LLM to read my datasheet"

Four reasons, and they are the whole product.

**1. Bit offsets get checked, not trusted.** Every extracted map goes through a
deterministic validator before a single line of C is emitted. Overlapping
bitfields, fields that overrun their register, reset values too wide for the
bits they sit in, enum values that do not fit, duplicate addresses — all caught
in pure Python, no model involved. A map with errors will not generate code
unless you pass `--force`.

```
[error  ] FIELD_OVERLAP          register CTRL_MEAS: bit 2 claimed by both 'OSRS_P' and 'MODE'
[error  ] FIELD_RESET_TOO_WIDE   CONFIG.T_SB: reset_value 0x9 does not fit in 3 bits
```

That list is the difference between generated code you can ship and generated
code you have to re-derive by hand anyway.

**2. It pays for each part once, and some parts are already paid for.**
Extracted maps are stored in a plain-JSON corpus keyed by part number, and the
corpus ships inside the wheel. So this works the moment you install, with no
API key and no datasheet:

```bash
pip install regforge
regforge gen BME280 --out ./src --driver    # no API call, no cost
```

Parts included today: **ADS1115, BME280, BMP280, DS3231, INA219, MCP23017,
MPU6050** — 100 registers. Anything you extract yourself joins your own layer
of the corpus, and your copy of a part always wins over the shipped one.

**3. The generated bit math ships with its own proof.** A generated header
always compiles — it is just `#define`s — so "it builds" tells you nothing about
whether `OSRS_T_SET` really writes bits 7:5. Pass `--tests` and RegForge emits
compile-time assertions derived from the same register map:

```bash
regforge gen BME280 --out ./src --tests
gcc -std=c99 -Wall -Wextra -Werror -c src/bme280_regs_test.c    # 173 assertions
```

Masks match their shift and width, fields stay inside their register, `SET`
lands the value at the right offset, `SET` preserves every neighbouring bit,
`GET(SET(x)) == x`, and an over-wide value cannot corrupt the field next door.
No hardware, no test runner. A mistake is a compile error naming the field:

```
error: size of array 'regforge_assert_bme280_ctrl_meas_osrs_t_mask_shape' is negative
   96 | REGFORGE_STATIC_ASSERT((BME280_CTRL_MEAS_OSRS_T_MASK) == ...
```

The assertions use the negative-array-size idiom rather than `_Static_assert`,
so they work on C99 toolchains — which is most embedded toolchains.

**4. It only sends the pages that matter.** A 200-page datasheet is roughly
150K tokens. The register map inside it is usually 8 to 25 pages. RegForge
finds those pages with local heuristics first, and you can see exactly what it
picked before spending anything:

```bash
regforge scan bst-bme280-ds002.pdf     # free, no API key needed
```

```
  page   score    hex   bits  selected
    26    8.41     37      9  <--
    27    8.02     41     12  <--
    28    7.55     28      7  <--
    12    2.10      6      0

selected 8 page(s): 24-31
extract with:  regforge extract bst-bme280-ds002.pdf --pages 24-31
```

---

## Install

```bash
pip install regforge
export ANTHROPIC_API_KEY=sk-ant-...
```

From source:

```bash
git clone https://github.com/MathewsV-Manoj/regforge && cd regforge
pip install -e ".[dev]"
python examples/seed_corpus.py      # writes the seed corpus
regforge gen BME280 --out ./out --driver
```

`scan`, `gen`, `check`, `list` and `verify` need no API key. Only `extract`
calls the model.

---

## What it generates

**`bme280_regs.h`** — addresses, widths, reset values, and per-field shift /
mask / get / set macros, with the datasheet's own bit notation kept in the
comments:

```c
/* CTRL_MEAS @ 0x00F4  rw  8-bit  reset 0x00 */
/* Pressure and temperature acquisition options, and the sensor mode. */

#define BME280_CTRL_MEAS                               0x00F4u
#define BME280_CTRL_MEAS_WIDTH                         8u
#define BME280_CTRL_MEAS_RESET                         0x00u

/*   MODE bits [1:0] rw reset 0x0 -- Sensor operating mode */
#define BME280_CTRL_MEAS_MODE_SHIFT                    0u
#define BME280_CTRL_MEAS_MODE_WIDTH                    2u
#define BME280_CTRL_MEAS_MODE_MASK                     0x03u
#define BME280_CTRL_MEAS_MODE_GET(reg)                 (((uint8_t)(reg) & 0x03u) >> 0u)
#define BME280_CTRL_MEAS_MODE_SET(reg, val)            (((uint8_t)(reg) & (uint8_t)~0x03u) | (((uint8_t)(val) << 0u) & 0x03u))
#define BME280_CTRL_MEAS_MODE_SLEEP                    0x00u  /* No measurements, minimum power */
#define BME280_CTRL_MEAS_MODE_FORCED                   0x01u  /* One measurement, then return to sleep */
#define BME280_CTRL_MEAS_MODE_NORMAL                   0x03u  /* Cycles between measuring and standby */
```

**`bme280.h` / `bme280.c`** (with `--driver`) — a bus-agnostic skeleton. Register
access, read-modify-write masking, burst reads and the chip-ID probe are
generated complete, and typed to the part's actual register width: a 16-bit
device like the ADS1115 gets a `uint16_t` accessor, not a `uint8_t` one that
would quietly read half a register. The two things a generator cannot know —
how *your* board talks I2C or SPI — are two function pointers you fill in:

```c
bme280_t dev;
bme280_init(&dev, my_i2c_read, my_i2c_write, &hi2c1);

if (bme280_probe(&dev) != 0) { /* CHIP_ID did not read 0x60 */ }

uint8_t ctrl = 0;
ctrl = BME280_CTRL_MEAS_OSRS_T_SET(ctrl, BME280_CTRL_MEAS_OSRS_T_X2);
ctrl = BME280_CTRL_MEAS_MODE_SET(ctrl, BME280_CTRL_MEAS_MODE_NORMAL);
bme280_write_reg(&dev, BME280_CTRL_MEAS, ctrl);
```

Generated code that pretends to know your HAL is worse than no generated code
at all, so RegForge does not pretend. The same applies to byte order: a
register map does not record whether a multi-byte register goes out MSB- or
LSB-first, so the driver documents its assumption (MSB first) and gives you a
`#define` to flip it, rather than guessing silently.

The drivers are compiled *and run* in CI against a fake transport, because
compiling only proves the macros parse — running is what proves the bytes come
back in the right order.

---

## The corpus

Extracted maps live as plain, sorted, git-diffable JSON in two layers:

```
regforge/corpus_data/        bundled, read-only, ships in the wheel
  bosch-sensortec/bme280.json
  texas-instruments/ads1115.json

./corpus  (or ~/.regforge/corpus)    yours, writable
  invensense/icm20948.json
```

Lookups check your layer first, so a map you verified against your own revision
of a datasheet is the one that generates. Writes — including `regforge verify`
on a part that shipped with the package — always land in your layer, never in
`site-packages`. `regforge list` shows which layer each part came from.

Machine extraction is a starting point, not an answer. When you have checked a
map against the datasheet, say so:

```bash
regforge verify BME280 --by "Mathews V Manoj" --notes "checked against DS002 rev 1.6"
```

Verified entries say so in the generated file's banner. Unverified ones carry
`NOT VERIFIED` in the same place — the same string in every generated file, so
one grep across a source tree finds everything unreviewed.

---

## Commands

| Command | What it does | Costs money |
|---|---|---|
| `regforge scan <pdf>` | show which pages look like a register map | no |
| `regforge extract <pdf>` | extract a map, validate it, save it | **yes** |
| `regforge gen <part>` | generate code from the corpus | no |
| `regforge gen <part> --tests` | + compile-time proof of the bit math | no |
| `regforge check <part>` | re-run validation on a stored map | no |
| `regforge list [query]` | list or search corpus entries | no |
| `regforge verify <part> --by X` | mark a map human-verified | no |
| `regforge stats` | corpus summary | no |

Useful flags: `--pages 24-31` when detection picks the wrong section,
`--model` to change extraction model, `--driver` to emit the driver skeleton,
`--tests` to emit the compile-time self-check, `--verbose` to see informational
findings, `--force` to generate from a map that failed validation.

---

## What it does not do yet

Being explicit, because the gap matters more than the feature list:

- **Scanned datasheets.** Extraction reads the PDF's own text and layout. A
  pure-image scan with no text layer will not work.
- **Memory-mapped MCU peripherals.** Built and tuned for I2C/SPI peripheral
  parts. An STM32 reference manual will produce something, but not something
  worth trusting yet.
- **Calibration and compensation.** RegForge extracts registers. It does not
  transcribe the compensation formulas that sit beside them.
- **Languages other than C.** Rust and Zephyr devicetree bindings are the
  obvious next targets.

---

## Status

Alpha. The schema in `models.py` is the contract everything else depends on;
expect it to move before 1.0.

If you extract a map for a part that is not in the corpus, a PR adding it is the
single most useful contribution — that is what makes the tool faster and cheaper
for the next person. See [CONTRIBUTING.md](CONTRIBUTING.md).

Every shipped part is currently **unverified**: hand-transcribed, validated
mechanically, but not yet checked against the datasheet by a human. Checking one
and running `regforge verify` is a real contribution too.

## Licence

Apache-2.0.
