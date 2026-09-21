# Launch checklist

Everything that can be done without your accounts is done. What is left needs
credentials only you have. This file is the runbook.

> Not committed advice: **do not launch and then disappear.** The first day of
> comments is where you find out whether the problem is real. Block two hours.

---

## 0. Before anything: the one unverified claim

`regforge extract` has never been run against a real datasheet, because there
was no API key on this machine. Everything around the model call is tested
(chunking, merge, truncation-retry, provenance, cost accounting — 27 tests with
a stubbed client), but extraction *quality* is unproven.

**Do this first. It is the only thing that can embarrass you on launch day.**

```bash
setx ANTHROPIC_API_KEY sk-ant-...     # new shell after this
```

Grab a datasheet you know well — the BME280 is ideal, because the corpus
already has a hand-transcribed map to diff against:

```bash
regforge scan bst-bme280-ds002.pdf
regforge extract bst-bme280-ds002.pdf --part BME280 --no-save --out /tmp/x --tests
```

Then compare against the seeded map. If extraction reproduces the bit offsets
you transcribed by hand, the core claim holds. If it does not, you have found
the real bug before 200 strangers did.

Try both models on the same datasheet and let the validator score them:

```bash
regforge extract ds.pdf --part X --model claude-sonnet-5 --no-save
regforge extract ds.pdf --part X --model claude-opus-5   --no-save
```

Compare error counts and bit coverage, then set the winner as the default in
`src/regforge/costs.py`. That is an evidence-based decision, not a guess — make
it before launch and you can answer "why Sonnet?" in the comments with data.

---

## 1. Publish the repo

```bash
cd C:\Users\Mathews\Documents\regforge
gh repo create regforge --public --source=. --remote=origin --push
```

Then, in the repo settings:

- **Description:** `Turn a datasheet into a verified register map and driver code.`
- **Topics:** `embedded`, `firmware`, `datasheet`, `code-generation`, `i2c`,
  `spi`, `register-map`, `c`, `claude`
- Replace `https://github.com/<you>/regforge` in `README.md` and
  `CONTRIBUTING.md` with the real URL.
- Check the Actions tab. All four CI jobs should pass. **If the negative test in
  `generated-code-compiles` fails, stop** — that means the self-check assertions
  are not load-bearing, which is the central claim of the project.

---

## 2. Publish to PyPI

Register the name first — it is free and stops someone else taking it.

```bash
python -m build
python -m twine upload dist/*
```

Use an API token, not a password. Then verify the thing a user actually does:

```bash
python -m venv /tmp/fresh
/tmp/fresh/bin/pip install regforge
/tmp/fresh/bin/regforge gen BME280 --out /tmp/out --driver --tests
```

CI already runs this against the built wheel on every push, but run it once by
hand against the *published* package.

---

## 3. Where to post

In this order, not all at once. Each one teaches you something you want before
the next.

| Where | When | Why |
|---|---|---|
| **r/embedded** | Day 1 | Your actual users. Highest-signal feedback, lowest stakes. |
| **Hacker News (Show HN)** | Day 2–3, Tue–Thu ~9am ET | Biggest reach. Go after r/embedded has caught the obvious flaws. |
| **r/FPGA, EEVblog, All About Circuits** | Day 3+ | Adjacent audiences, slower burn. |
| **LinkedIn** | Anytime | Your network, and it compounds for internships. |

Do **not** post to all of them the same hour. If the first comment thread finds
a real bug, you want to fix it before the big audience arrives.

---

## 4. Post drafts

Edit these. They should sound like you, not like a press release.

### r/embedded

> **Title:** I got tired of retyping register maps out of datasheets, so I built a tool that does it and proves the bit math
>
> Every time I bring up a new sensor I lose an afternoon retyping register
> tables into a header, and at least once per part I get a bit offset backwards
> and find out on a logic analyser.
>
> So: `regforge extract datasheet.pdf --part BME280 --out ./src --driver`
>
> It finds the register pages, extracts the map, and generates a header plus a
> bus-agnostic driver skeleton. Two things I think make it different from "ask
> an LLM to read my datasheet":
>
> **It validates before it generates.** Overlapping bitfields, fields that
> overrun their register, reset values too wide for the bits they sit in — all
> caught deterministically in Python, no model involved. A map with errors will
> not generate code.
>
> **It emits compile-time assertions for the bit math.** `--tests` generates a
> C file of static assertions derived from the same map: masks match their shift
> and width, `SET` lands at the right offset, `SET` preserves neighbouring bits,
> `GET(SET(x)) == x`. Compile it and the compiler tells you if the macros are
> wrong. CI includes a negative test that corrupts a mask and asserts the
> self-check refuses to compile, so the assertions can't quietly become
> decorative.
>
> Seven parts ship with it (BME280, BMP280, MPU6050, ADS1115, INA219, DS3231,
> MCP23017) so `pip install regforge && regforge gen BME280` works with no API
> key and no datasheet. Generated code compiles clean under
> `-Wall -Wextra -Wpedantic -Werror` on riscv32-esp-elf and xtensa-esp32-elf.
>
> **Honest limitations:** the shipped maps are hand-transcribed and *not yet
> human-verified against the datasheets* — validated mechanically, but I would
> not stake your bring-up on them without checking. It does not handle
> image-only scanned PDFs, MCU peripheral reference manuals, or compensation
> formulas.
>
> Apache-2.0, GitHub link in comments. I'd genuinely like to know: is
> retyping register maps a real recurring cost for you, or did I just build a
> tool for my own bad week?

The last line matters. You are not farming upvotes, you are testing whether the
problem is real. Read every reply.

### Show HN

> **Title:** Show HN: RegForge – Datasheet to register map to C driver, with compile-time proof
>
> Bringing up a new sensor means retyping register tables out of a 180-page PDF
> into a header, and getting `[7:5]` to mean shift 5 width 3 every single time.
> Get one backwards and you lose a day on a logic analyser.
>
> RegForge extracts the register map with Claude, validates it deterministically,
> and generates a C header plus a bus-agnostic driver skeleton.
>
> The part I actually care about: a generated header always compiles, because
> it's just `#define`s — so "it builds" tells you nothing about whether the
> macros are right. `--tests` emits static assertions derived from the same map
> (mask shape, SET offset, neighbour preservation, GET/SET round-trip), so the
> compiler checks the bit arithmetic instead of you trusting it. CI corrupts a
> mask on purpose and fails the build if the self-check still compiles.
>
> It also only sends the register pages, not the whole PDF — local heuristics
> pick them, and `regforge scan` shows you the choice for free before you spend
> anything. Extracted maps go into a corpus that ships in the wheel, so the
> second person to want a BME280 pays nothing.
>
> Seven parts included. The shipped maps are mechanically validated but not yet
> human-verified — that's the top of the contributing list, and the banner in
> every generated file says so.
>
> I'm an ECE undergrad and this started as my own annoyance. Curious whether it
> maps onto anyone else's workflow.

**Show HN rules:** post it yourself, no marketing language, be in the thread
answering for the first few hours. Do not ask for upvotes anywhere.

### LinkedIn

> Shipped something small and real this week.
>
> Bringing up a new sensor means retyping register tables out of a 180-page
> datasheet into a header file, getting every bit offset right by hand. I built
> RegForge to do it — and, more usefully, to *prove* it did it correctly: it
> generates compile-time assertions for the bit arithmetic, so the compiler
> catches a wrong mask instead of a logic analyser catching it three days later.
>
> Open source, Apache-2.0. Seven parts ship with it. Built solo alongside my
> 5th semester.
>
> Would love feedback from anyone doing embedded work: [link]

---

## 5. What to watch in the first week

You are measuring one thing: **does anyone use it twice?**

| Signal | Means |
|---|---|
| Stars | Almost nothing. People star and forget. |
| PyPI downloads, day 2–7 | Better. Day-1 downloads are curiosity. |
| **A corpus PR from a stranger** | The strongest possible signal. The flywheel works. |
| "Does it support \<my part\>" | Real demand. Answer every one, add the part. |
| Silence on r/embedded | The pain is not as common as you think. Believe it. |

**The kill criterion, from the plan — write it down and honour it:** if after 90
days fewer than 5 people have voluntarily used it twice, the problem is not real
enough. Stop, keep the freelance income, pick another wedge. Pre-committing now
is what stops this quietly eating a year.

---

## 6. If it works: the next three things

1. **Ship more parts.** The corpus is the moat and it has seven entries. Fifty
   makes it a default; seven makes it a demo.
2. **Verify the shipped maps.** `verified: yes` is the thing nobody else can
   copy cheaply, because it costs human attention.
3. **Then, and only then, a hosted tier.** A shared team corpus, CI integration,
   $29/mo. Not before people are using the free CLI on their own.

Do not build the hosted tier first. The free tool is what earns the right to
charge for anything.
