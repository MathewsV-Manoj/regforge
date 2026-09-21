"""Build a static site from the corpus.

The strategic point: embedded engineers do not search for "datasheet to driver
tool". They search for "BME280 register map" and "MPU6050 WHO_AM_I address".
The corpus is already the best structured answer to those queries -- it is just
sitting in JSON where no search engine will ever find it.

So every part gets a page. The page answers the query properly (full register
table, bit layouts, reset values) and then mentions that the same data installs
as a C header in one command. That is not a marketing page with a keyword
stapled on; it is genuinely the thing the person wanted, which is the only
durable way to rank.

Each page also carries JSON-LD, so answer engines have something structured to
cite rather than scraping a table.

    python tools/build_site.py            # writes ./site
    python tools/build_site.py --out docs # or wherever
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from regforge import __version__  # noqa: E402
from regforge.corpus import Corpus, slug  # noqa: E402
from regforge.models import DeviceRecord  # noqa: E402
from regforge.validate import coverage_score  # noqa: E402

GITHUB = "https://github.com/MathewsV-Manoj/regforge"
SITE_NAME = "RegForge"

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#fbfaf8; --surface:#fff; --border:#e5e1da; --text:#1c1a17;
  --muted:#6b6560; --accent:#b4532a; --accent-soft:#fdf0e9;
  --code-bg:#f5f2ee; --ok:#2f6f4f; --warn:#8a6d1f;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#161513; --surface:#1e1d1a; --border:#332f2a; --text:#eae6e0;
    --muted:#9a938b; --accent:#e08a5f; --accent-soft:#2a201a;
    --code-bg:#211f1c; --ok:#6bbd91; --warn:#d6b25f;
  }
}
:root[data-theme="dark"]{
  --bg:#161513; --surface:#1e1d1a; --border:#332f2a; --text:#eae6e0;
  --muted:#9a938b; --accent:#e08a5f; --accent-soft:#2a201a;
  --code-bg:#211f1c; --ok:#6bbd91; --warn:#d6b25f;
}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--bg);color:var(--text);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;
  overflow-x:hidden;
}
.wrap{max-width:900px;margin:0 auto;padding:0 16px}
header.site{border-bottom:1px solid var(--border);background:var(--surface)}
header.site .wrap{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding-top:14px;padding-bottom:14px}
.brand{font-weight:700;letter-spacing:-.02em;text-decoration:none;color:var(--text);font-size:18px}
.brand span{color:var(--accent)}
header.site nav{margin-left:auto;display:flex;gap:18px;flex-wrap:wrap}
header.site nav a{color:var(--muted);text-decoration:none;font-size:14px}
header.site nav a:hover{color:var(--accent)}
h1{font-size:clamp(26px,5vw,38px);line-height:1.15;letter-spacing:-.03em;margin:28px 0 8px}
h2{font-size:22px;letter-spacing:-.02em;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--border)}
h3{font-size:16px;margin:26px 0 8px;font-family:var(--mono);color:var(--accent)}
p{margin:0 0 14px}
a{color:var(--accent)}
.lede{font-size:18px;color:var(--muted);margin-bottom:22px}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 24px}
.chip{
  font-size:12px;font-family:var(--mono);padding:4px 9px;border-radius:99px;
  background:var(--accent-soft);color:var(--accent);border:1px solid var(--border);
  white-space:nowrap;
}
.chip.ok{color:var(--ok)} .chip.warn{color:var(--warn)}
pre{
  background:var(--code-bg);border:1px solid var(--border);border-radius:8px;
  padding:14px;overflow-x:auto;font-family:var(--mono);font-size:13px;line-height:1.5;margin:0 0 16px;
}
code{font-family:var(--mono);font-size:.9em;background:var(--code-bg);padding:1px 5px;border-radius:4px}
pre code{background:none;padding:0;font-size:inherit}
.tablewrap{overflow-x:auto;margin:0 0 18px;border:1px solid var(--border);border-radius:8px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:520px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border)}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:none}
td.mono,th.mono{font-family:var(--mono);font-size:13px;white-space:nowrap}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));margin:0 0 24px}
.card{
  display:block;padding:16px;border:1px solid var(--border);border-radius:10px;
  background:var(--surface);text-decoration:none;color:inherit;transition:border-color .15s,transform .15s;
}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card .pn{font-family:var(--mono);font-weight:700;color:var(--accent);font-size:15px}
.card .mf{font-size:13px;color:var(--muted);margin-top:2px}
.card .st{font-size:12px;color:var(--muted);margin-top:8px;font-family:var(--mono)}
.note{
  border-left:3px solid var(--accent);background:var(--accent-soft);
  padding:12px 14px;border-radius:0 8px 8px 0;margin:0 0 20px;font-size:14px;
}
.fields{margin:0 0 20px}
details{border:1px solid var(--border);border-radius:8px;background:var(--surface);margin-bottom:8px}
summary{padding:10px 14px;cursor:pointer;font-family:var(--mono);font-size:14px}
summary::marker{color:var(--accent)}
details[open] summary{border-bottom:1px solid var(--border)}
details .inner{padding:12px 14px}
footer.site{border-top:1px solid var(--border);margin-top:56px;padding:24px 0 40px;color:var(--muted);font-size:14px}
footer.site a{color:var(--muted)}
.crumb{font-size:14px;color:var(--muted);margin:20px 0 0}
.crumb a{color:var(--muted);text-decoration:none}
.crumb a:hover{color:var(--accent)}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def page(title: str, description: str, body: str, *, canonical: str, jsonld: dict | None = None) -> str:
    ld = (
        f'<script type="application/ld+json">{json.dumps(jsonld, separators=(",", ":"))}</script>'
        if jsonld
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<style>{CSS}</style>
{ld}
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="../index.html">Reg<span>Forge</span></a>
  <nav>
    <a href="../index.html">Parts</a>
    <a href="{GITHUB}">GitHub</a>
    <a href="{GITHUB}/blob/main/CONTRIBUTING.md">Contribute</a>
  </nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
  <p>{SITE_NAME} {esc(__version__)} &middot; Apache-2.0 &middot;
     <a href="{GITHUB}">github.com/MathewsV-Manoj/regforge</a></p>
  <p>Register data is transcribed from manufacturer datasheets. Always verify
     against the official datasheet before relying on it in a design.</p>
</div></footer>
</body>
</html>
"""


def bit_span(f) -> str:
    return f"[{f.bit_high}:{f.bit_offset}]" if f.bit_width > 1 else f"[{f.bit_offset}]"


def hexv(v, bits=8) -> str:
    if v is None:
        return "&mdash;"
    return f"0x{v:0{max(2, (bits + 3) // 4)}X}"


def render_part(rec: DeviceRecord) -> tuple[str, str, str]:
    d, p = rec.device, rec.provenance
    pn = d.part_number
    addr_bits = d.register_address_bits

    title = f"{pn} register map — addresses, bitfields and C header | RegForge"
    desc = (
        f"Complete {pn} register map from {d.manufacturer}: "
        f"{len(d.registers)} registers with addresses, bit positions, reset values and "
        f"bitfield layouts. Generate a C header and driver with one command."
    )

    status = (
        f'<span class="chip ok">verified by {esc(p.verified_by)}</span>'
        if p.verified
        else '<span class="chip warn">not yet human-verified</span>'
    )
    addrs = ", ".join(f"0x{a:02X}" for a in d.i2c_addresses)

    parts = [
        f'<p class="crumb"><a href="../index.html">All parts</a> / {esc(pn)}</p>',
        f"<h1>{esc(pn)} register map</h1>",
        f'<p class="lede">{esc(d.description or "")} &mdash; {esc(d.manufacturer)}</p>',
        '<div class="meta">',
        f'<span class="chip">{len(d.registers)} registers</span>',
        f'<span class="chip">{esc(", ".join(b.value.upper() for b in d.buses))}</span>',
        (f'<span class="chip">I²C {esc(addrs)}</span>' if addrs else ""),
        f'<span class="chip">{addr_bits}-bit addresses</span>',
        f'<span class="chip">{coverage_score(d) * 100:.0f}% bit coverage</span>',
        status,
        "</div>",
    ]

    parts.append("<h2>Get it as a C header</h2>")
    parts.append(
        "<pre><code>pip install regforge\n"
        f"regforge gen {esc(pn)} --out ./src --driver --tests</code></pre>"
    )
    parts.append(
        '<p>That writes <code>%s_regs.h</code> (every address, mask and shift below), a '
        "bus-agnostic driver skeleton, and a file of compile-time assertions that make your "
        "compiler check the bit arithmetic. No API key needed &mdash; this part ships inside "
        "the package.</p>" % esc(slug(pn).replace("-", "_"))
    )

    if not p.verified:
        parts.append(
            '<div class="note"><strong>Not yet human-verified.</strong> This map is '
            "transcribed and mechanically validated (no overlapping fields, no out-of-range "
            "bits, reset values consistent with their fields), but nobody has checked it "
            f'line-by-line against the datasheet yet. <a href="{GITHUB}/blob/main/CONTRIBUTING.md">'
            "Verifying it</a> is a genuinely useful half hour.</div>"
        )

    parts.append("<h2>Registers</h2>")
    parts.append('<div class="tablewrap"><table><thead><tr>')
    parts.append(
        '<th class="mono">Address</th><th class="mono">Register</th><th>Access</th>'
        '<th class="mono">Width</th><th class="mono">Reset</th><th>Description</th>'
    )
    parts.append("</tr></thead><tbody>")
    for r in d.registers:
        parts.append(
            f'<tr><td class="mono">{hexv(r.address, addr_bits)}</td>'
            f'<td class="mono">{esc(r.name)}</td>'
            f"<td>{esc(r.access.value.upper())}</td>"
            f'<td class="mono">{r.size_bits}</td>'
            f'<td class="mono">{hexv(r.reset_value, r.size_bits)}</td>'
            f"<td>{esc(r.description or '')}</td></tr>"
        )
    parts.append("</tbody></table></div>")

    with_fields = [r for r in d.registers if r.fields]
    if with_fields:
        parts.append("<h2>Bitfields</h2>")
        parts.append(
            "<p>Bit positions are the thing people get backwards. "
            "<code>[7:5]</code> means shift 5, width 3, mask 0xE0.</p>"
        )
        parts.append('<div class="fields">')
        for r in with_fields:
            parts.append(
                f"<details><summary>{esc(r.name)} &nbsp;@&nbsp; {hexv(r.address, addr_bits)} "
                f"&nbsp;&mdash;&nbsp; {len(r.fields)} fields</summary><div class='inner'>"
            )
            parts.append('<div class="tablewrap"><table><thead><tr>')
            parts.append(
                '<th class="mono">Bits</th><th class="mono">Field</th><th>Access</th>'
                '<th class="mono">Mask</th><th class="mono">Reset</th><th>Description</th>'
            )
            parts.append("</tr></thead><tbody>")
            for f in r.fields:
                parts.append(
                    f'<tr><td class="mono">{bit_span(f)}</td>'
                    f'<td class="mono">{esc(f.name)}</td>'
                    f"<td>{esc(f.access.value.upper())}</td>"
                    f'<td class="mono">{hexv(f.mask, r.size_bits)}</td>'
                    f'<td class="mono">{hexv(f.reset_value, f.bit_width)}</td>'
                    f"<td>{esc(f.description or '')}</td></tr>"
                )
            parts.append("</tbody></table></div>")

            enum_fields = [f for f in r.fields if f.enum_values]
            for f in enum_fields:
                parts.append(f"<h3>{esc(r.name)}.{esc(f.name)} values</h3>")
                parts.append('<div class="tablewrap"><table><thead><tr>')
                parts.append('<th class="mono">Value</th><th class="mono">Name</th><th>Meaning</th>')
                parts.append("</tr></thead><tbody>")
                for ev in f.enum_values:
                    parts.append(
                        f'<tr><td class="mono">{hexv(ev.value, max(4, f.bit_width))}</td>'
                        f'<td class="mono">{esc(ev.name)}</td>'
                        f"<td>{esc(ev.description or '')}</td></tr>"
                    )
                parts.append("</tbody></table></div>")
            parts.append("</div></details>")
        parts.append("</div>")

    parts.append("<h2>Source</h2>")
    src = p.source_filename or "unknown"
    how = "machine-extracted" if p.extraction_model else "hand-transcribed"
    parts.append(
        f"<p>Transcribed from <strong>{esc(src)}</strong> ({how}"
        + (f", {esc(p.extraction_model)}" if p.extraction_model else "")
        + "). "
        + (f"{esc(p.notes)}" if p.notes else "")
        + "</p>"
    )
    parts.append(
        f'<p><a href="{GITHUB}/blob/main/corpus/{slug(d.manufacturer)}/{slug(pn)}.json">'
        "View the raw JSON</a> &middot; "
        f'<a href="{GITHUB}/issues/new?title=Correction%3A+{esc(pn)}">Report an error</a></p>'
    )

    jsonld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": f"{pn} register map",
        "about": {"@type": "Product", "name": pn, "manufacturer": {"@type": "Organization", "name": d.manufacturer}},
        "description": desc,
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
        "isAccessibleForFree": True,
    }
    return title, desc, page(title, desc, "\n".join(parts), canonical=f"parts/{slug(pn)}.html", jsonld=jsonld)


def render_index(records: list[DeviceRecord]) -> str:
    title = "RegForge — register maps and generated C drivers for embedded parts"
    desc = (
        "Open register maps for common I²C and SPI parts, with addresses, bitfields and "
        "reset values. Generate a C header, driver skeleton and compile-time proof of the "
        "bit math with one command."
    )
    total_regs = sum(len(r.device.registers) for r in records)

    body = [
        "<h1>Register maps that generate their own C headers</h1>",
        '<p class="lede">Every part below is a complete, machine-validated register map. '
        "Read it here, or install it as a C header in one command.</p>",
        "<pre><code>pip install regforge\nregforge gen BME280 --out ./src --driver --tests</code></pre>",
        '<div class="meta">'
        f'<span class="chip">{len(records)} parts</span>'
        f'<span class="chip">{total_regs} registers</span>'
        '<span class="chip">Apache-2.0</span>'
        "</div>",
        "<h2>Parts</h2>",
        '<div class="grid">',
    ]
    for rec in sorted(records, key=lambda r: slug(r.device.part_number)):
        d = rec.device
        body.append(
            f'<a class="card" href="parts/{slug(d.part_number)}.html">'
            f'<div class="pn">{esc(d.part_number)}</div>'
            f'<div class="mf">{esc(d.manufacturer)}</div>'
            f'<div class="st">{len(d.registers)} registers &middot; '
            f'{esc(", ".join(b.value.upper() for b in d.buses))}</div></a>'
        )
    body.append("</div>")

    body += [
        "<h2>Why this exists</h2>",
        "<p>Bringing up an unfamiliar chip means retyping register tables out of a "
        "180-page PDF into a header file, and getting every bit offset right by hand. "
        "<code>[7:5]</code> means shift 5 and width 3; get it backwards and you lose a day "
        "on a logic analyser, because nothing tells you.</p>",
        "<p>RegForge reads those pages, validates the result deterministically, and "
        "generates the header plus a driver skeleton. Crucially it also emits compile-time "
        "assertions derived from the same map, so a wrong mask is a <em>build failure</em> "
        "naming the field &mdash; not a silent hardware bug.</p>",
        "<h2>Missing a part?</h2>",
        "<p>Point it at the datasheet:</p>",
        "<pre><code>regforge scan datasheet.pdf          # free, shows which pages it will read\n"
        "regforge extract datasheet.pdf --part XYZ</code></pre>",
        f'<p>Then <a href="{GITHUB}/blob/main/CONTRIBUTING.md">contribute it back</a> and '
        "it becomes free and instant for everyone after you. That is the whole idea: each "
        "part gets paid for once.</p>",
    ]

    jsonld = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "RegForge",
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Windows, macOS, Linux",
        "description": desc,
        "url": GITHUB,
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }
    out = page(title, desc, "\n".join(body), canonical="index.html", jsonld=jsonld)
    # The index sits one level above the part pages.
    return out.replace('href="../index.html"', 'href="index.html"')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / "site"))
    ap.add_argument("--corpus", default=str(REPO / "corpus"))
    args = ap.parse_args(argv)

    corpus = Corpus(args.corpus, include_bundled=False)
    entries = corpus.list_all()
    if not entries:
        print("error: corpus is empty", file=sys.stderr)
        return 1

    out = Path(args.out)
    (out / "parts").mkdir(parents=True, exist_ok=True)

    records = [corpus.load_path(e.path) for e in entries]

    urls = ["index.html"]
    for rec in records:
        _, _, doc = render_part(rec)
        name = f"parts/{slug(rec.device.part_number)}.html"
        (out / name).write_text(doc, encoding="utf-8")
        urls.append(name)
        print(f"  {name}")

    (out / "index.html").write_text(render_index(records), encoding="utf-8")
    print("  index.html")

    # Sitemap and robots, so crawlers find every part page.
    today = date.today().isoformat()
    base = "https://mathewsv-manoj.github.io/regforge/"
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"<url><loc>{base}{u}</loc><lastmod>{today}</lastmod></url>")
    sm.append("</urlset>")
    (out / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    print(f"\n{len(records)} part pages + index -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
