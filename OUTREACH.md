# Outreach

Who to contact, what to say, and — importantly — who *not* to contact.

---

## Do not cold-email chip manufacturers

You asked for this and I think it is a mistake. Three reasons, in order of how
much they should worry you.

**1. There is no upside.** What would Bosch or TI actually do? They do not
promote third-party tools from people with no users. Their developer-relations
teams exist to sell chips, and a driver-generation tool does not move that
needle for them. The realistic best case is that nobody replies.

**2. There is a real downside.** You are emailing a large semiconductor company
to say, in effect, *"I built a tool that ingests your copyrighted datasheets and
republishes structured data extracted from them."* Register addresses and bit
positions are facts, and facts are generally not copyrightable — so the project
is on reasonable ground — but "reasonable ground" is a thing you want to be
standing on quietly, not a thing you want to invite a legal team to evaluate.
Especially as a student with no company behind you and nothing to gain from the
conversation.

**3. It is the wrong order.** Manufacturer relationships happen *after* you have
users, and they happen through field application engineers and developer
relations people who found you — not through cold email to
`info@`. Get 500 GitHub stars and a few companies using it, and that
conversation becomes possible on completely different terms.

**What to do instead:** nothing, for now. Revisit in six months if the project
has traction.

---

## The gate — read this before sending anything

Do not send a single one of these emails until **both** are true:

1. **`regforge extract` has been run on a real datasheet and works.** It is the
   headline feature and it has never run. If Hackaday covers you and the main
   feature is broken, that is a one-shot burn — they will not write about you
   twice.
2. **There is a demo GIF at the top of the README.** Every outlet below is
   visual. A wall of text gets skimmed and dropped.

The GIF should be roughly 40 seconds:

1. An obscure part with no existing library
2. `regforge extract weird.pdf --part XYZ --out ./src --driver --tests`
3. Files appear
4. `gcc ... -Werror` compiles clean
5. **You edit a mask to a wrong value by hand and recompile — the build fails,
   naming the field**

Step 5 is the one people share. Record with `asciinema` or OBS.

---

## Tier 1 — highest leverage, send first

### Hackaday — `tips@hackaday.com`

The single biggest lever available to you. They publish reader tips daily, the
audience is exactly embedded people, and one post is a permanent, linkable
credential that outlasts any Reddit thread.

Their own submission advice: **avoid press releases.** Write like a person who
is excited about a specific thing.

> **Subject:** A tool that reads datasheets and then proves it didn't make the register map up
>
> Hi,
>
> I'm an ECE undergrad in Kerala. I kept losing afternoons retyping register
> tables out of datasheets into headers, and losing days when I got a bit
> offset backwards, so I built RegForge.
>
> `regforge extract datasheet.pdf --part XYZ --out ./src --driver --tests`
>
> The bit I think your readers will care about isn't the extraction — anyone can
> point an LLM at a PDF. It's that generated code you can't trust is worthless,
> so it emits a C file of compile-time assertions derived from the same register
> map: masks match their shift and width, SET lands at the right offset, SET
> preserves neighbouring bits, GET(SET(x)) == x.
>
> Change a mask to a wrong value and the build fails, naming the field:
>
>     error: size of array 'regforge_assert_bme280_ctrl_meas_osrs_t_mask_shape' is negative
>
> CI corrupts a mask on purpose and fails if the self-check still compiles, so
> the assertions can't quietly become decorative. The generated drivers are also
> compiled and run against a fake transport, because compiling a header proves
> nothing about whether the driver reassembles bytes in the right order.
>
> Seven parts ship with it, so `pip install regforge && regforge gen BME280`
> works with no API key and no datasheet. Output compiles clean under
> -Wall -Wextra -Wpedantic -Werror on riscv32-esp-elf and xtensa-esp32-elf.
>
> Apache-2.0: https://github.com/MathewsV-Manoj/regforge
>
> Happy to answer anything.
>
> Mathews V Manoj

### Jay Carlson — via the contact link on `jaycarlson.net`

Wrote the definitive cheap-MCU roundups. Deeply technical, reads datasheets for
fun, and his audience is precisely the people who hit "no library exists for
this part." He is exactly the reader this tool was built for. Keep it short —
he will judge it on the engineering, not the pitch.

### Interrupt (Memfault) — post on `community.memfault.com`, don't email

This is a community forum, so posting is the right move rather than cold email.
Serious firmware engineers, and their blog regularly rounds up tools they liked.
If it lands there organically it can get picked up.

---

## Tier 2 — after Tier 1 has landed

| Target | Channel | Why |
|---|---|---|
| **Embedded.fm** (Elecia White) | contact form on embedded.fm | Podcast, has a tools tag, interviews people doing exactly this |
| **The Amp Hour** | contact form | Chris Gammell's audience is hardware-heavy |
| **Hackster.io** | publish a project page | Publishes tools, good SEO, low effort |
| **Phil's Lab** (YouTube) | YouTube business email | Large PCB/firmware audience |
| **Adafruit** | Discord / "Python on Hardware" newsletter tip | They love tooling. Note they also *write* libraries, so frame it as complementary — obscure parts they will never cover |
| **PlatformIO / Zephyr** communities | Discourse / Discord | Integration angle: generated drivers dropping into their build systems |

---

## Tier 3 — the one that actually compounds

**Answer every "does it support &lt;my part&gt;?" by adding that part the same day.**

This is not glamorous and it beats every email above. Each question is a real
user telling you exactly what to build. Add the part, reply with a link, and you
have converted a question into a user *and* a corpus entry. Twenty of those and
people start recommending you unprompted, which is the only marketing that
compounds.

---

## Tone rules for all of it

- **No press-release voice.** "Revolutionary AI-powered solution" gets deleted.
- **Lead with the problem, not the tool.** Every embedded person has lost a day
  to a wrong bit offset. Start there.
- **Say what it does not do.** Naming the limitations is what makes the rest
  believable. It does not handle scanned PDFs, MCU reference manuals, or
  command-based chips, and the shipped maps are not human-verified yet.
- **Be the student.** "I'm an ECE undergrad and this was my own bad week" is
  true, and it buys goodwill that no marketing copy can.
- **One link. No attachments.** Attachments from strangers get binned.
