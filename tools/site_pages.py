"""Page renderers for the generated site.

Everything here is derived from the corpus rather than written by hand, so the
site grows automatically as parts are added and can never drift out of step
with the data the tool actually ships.
"""

from __future__ import annotations

import json

from regforge.corpus import slug
from regforge.models import DeviceRecord
from regforge.validate import coverage_score

from site_theme import GITHUB, bit_diagram, bit_span, esc, hexv, page

# Pairs worth a side-by-side. Chosen because these are the parts people
# actually confuse, and confusing them produces a driver that almost works.
COMPARE_PAIRS = [
    ("BME280", "BMP280"),
    ("DS1307", "DS3231"),
    ("INA219", "INA226"),
    ("MCP23008", "MCP23017"),
    ("ADXL345", "LIS3DH"),
]


# ---------------------------------------------------------------------------
# part page
# ---------------------------------------------------------------------------

def pick_related(rec, all_records, limit: int = 3):
    me = slug(rec.device.part_number)
    same = [
        r for r in all_records
        if slug(r.device.part_number) != me
        and slug(r.device.manufacturer) == slug(rec.device.manufacturer)
    ]
    others = [r for r in all_records if slug(r.device.part_number) != me and r not in same]
    return (same + others)[:limit]


def render_part(rec: DeviceRecord, related=None, address_clashes=None) -> str:
    d, p = rec.device, rec.provenance
    related = related or []
    address_clashes = address_clashes or {}
    pn = d.part_number
    ab = d.register_address_bits

    title = f"{pn} register map — addresses, bitfields and C header | RegForge"
    desc = (
        f"Complete {pn} register map from {d.manufacturer}: {len(d.registers)} registers "
        f"with addresses, bit positions, masks, reset values and bitfield layouts. "
        f"Generate a C header and driver with one command."
    )

    status = (
        f'<span class="chip ok">verified by {esc(p.verified_by)}</span>'
        if p.verified
        else '<span class="chip warn">not yet human-verified</span>'
    )
    addrs = ", ".join(f"0x{a:02X}" for a in d.i2c_addresses)

    out = [
        f'<p class="crumb"><a href="../index.html">All parts</a> / {esc(pn)}</p>',
        f"<h1>{esc(pn)} register map</h1>",
        f'<p class="lede">{esc(d.description or "")} &mdash; {esc(d.manufacturer)}</p>',
        '<div class="meta">',
        f'<span class="chip">{len(d.registers)} registers</span>',
        f'<span class="chip">{esc(", ".join(b.value.upper() for b in d.buses))}</span>',
        (f'<span class="chip">I²C {esc(addrs)}</span>' if addrs else ""),
        f'<span class="chip">{ab}-bit reg addresses</span>',
        f'<span class="chip">{coverage_score(d) * 100:.0f}% bit coverage</span>',
        status,
        "</div>",
    ]

    # Bus-conflict warning. This is the single most useful thing the corpus can
    # tell someone wiring a board: two of these parts cannot share a bus.
    clashes = []
    for a in d.i2c_addresses:
        for other in address_clashes.get(a, []):
            if slug(other) != slug(pn):
                clashes.append((a, other))
    if clashes:
        by_part: dict[str, list[int]] = {}
        for a, other in clashes:
            by_part.setdefault(other, []).append(a)
        items = "; ".join(
            f'<a href="{slug(o)}.html">{esc(o)}</a> (' + ", ".join(f"0x{a:02X}" for a in sorted(set(v))) + ")"
            for o, v in sorted(by_part.items())
        )
        out.append(
            '<div class="note danger"><strong>I²C address conflict.</strong> '
            f"On its default address(es) this part collides with {items}. "
            "You cannot put them on the same bus without changing a strap pin, using an I²C "
            'multiplexer, or moving one to a second bus. '
            '<a href="../i2c-addresses.html">See the full address map</a>.</div>'
        )

    out.append("<h2>Get it as a C header</h2>")
    out.append(
        "<pre><code>pip install regforge\n"
        f"regforge gen {esc(pn)} --out ./src --driver --tests</code></pre>"
    )
    stem = slug(pn).replace("-", "_")
    out.append(
        f"<p>Writes <code>{esc(stem)}_regs.h</code> with every address, mask and shift below, "
        "a bus-agnostic driver skeleton, and a file of compile-time assertions that make your "
        "compiler check the bit arithmetic. No API key needed &mdash; this part ships inside "
        "the package.</p>"
    )

    if not p.verified:
        out.append(
            '<div class="note"><strong>Not yet human-verified.</strong> Transcribed and '
            "mechanically validated &mdash; no overlapping fields, no out-of-range bits, reset "
            "values consistent with their fields &mdash; but not yet checked line-by-line "
            f'against the datasheet. <a href="{GITHUB}/blob/main/CONTRIBUTING.md">Verifying it</a> '
            "is a useful half hour.</div>"
        )

    # registers table
    out.append("<h2>Registers</h2>")
    out.append('<div class="tablewrap"><table><thead><tr>')
    out.append(
        '<th class="mono">Addr</th><th class="mono">Register</th><th>Access</th>'
        '<th class="mono">Width</th><th class="mono">Reset</th><th>Description</th>'
    )
    out.append("</tr></thead><tbody>")
    for r in d.registers:
        out.append(
            f'<tr><td class="mono">{hexv(r.address, ab)}</td>'
            f'<td class="mono">{esc(r.name)}</td>'
            f"<td>{esc(r.access.value.upper())}</td>"
            f'<td class="mono">{r.size_bits}</td>'
            f'<td class="mono">{hexv(r.reset_value, r.size_bits)}</td>'
            f"<td>{esc(r.description or '')}</td></tr>"
        )
    out.append("</tbody></table></div>")

    # bit layouts
    with_fields = [r for r in d.registers if r.fields]
    if with_fields:
        out.append("<h2>Bit layouts</h2>")
        out.append(
            "<p>Drawn MSB-first, the way the datasheet draws them. "
            "<code>[7:5]</code> means shift 5, width 3, mask 0xE0 &mdash; this is the notation "
            "that costs people a day when they read it backwards.</p>"
        )
        for r in with_fields:
            out.append(
                f"<details><summary>{esc(r.name)} &nbsp;@&nbsp; {hexv(r.address, ab)} "
                f"&nbsp;&mdash;&nbsp; {len(r.fields)} fields</summary><div class='inner'>"
            )
            out.append(bit_diagram(r))
            out.append('<div class="tablewrap"><table><thead><tr>')
            out.append(
                '<th class="mono">Bits</th><th class="mono">Field</th><th>Access</th>'
                '<th class="mono">Mask</th><th class="mono">Reset</th><th>Description</th>'
            )
            out.append("</tr></thead><tbody>")
            for f in r.fields:
                out.append(
                    f'<tr><td class="mono">{bit_span(f)}</td>'
                    f'<td class="mono">{esc(f.name)}</td>'
                    f"<td>{esc(f.access.value.upper())}</td>"
                    f'<td class="mono">{hexv(f.mask, r.size_bits)}</td>'
                    f'<td class="mono">{hexv(f.reset_value, f.bit_width)}</td>'
                    f"<td>{esc(f.description or '')}</td></tr>"
                )
            out.append("</tbody></table></div>")

            for f in [x for x in r.fields if x.enum_values]:
                out.append(f"<h3>{esc(r.name)}.{esc(f.name)} values</h3>")
                out.append('<div class="tablewrap"><table><thead><tr>')
                out.append('<th class="mono">Value</th><th class="mono">Name</th><th>Meaning</th>')
                out.append("</tr></thead><tbody>")
                for ev in f.enum_values:
                    out.append(
                        f'<tr><td class="mono">{hexv(ev.value, max(4, f.bit_width))}</td>'
                        f'<td class="mono">{esc(ev.name)}</td>'
                        f"<td>{esc(ev.description or '')}</td></tr>"
                    )
                out.append("</tbody></table></div>")
            out.append("</div></details>")

    # generated header excerpt
    example = max(d.registers, key=lambda r: len(r.fields), default=None)
    if example is not None and example.fields:
        from regforge.codegen.c_header import generate_regs_header

        full = generate_regs_header(rec).splitlines()
        marker = f"/* {example.name} @"
        start = next((i for i, ln in enumerate(full) if ln.startswith(marker)), None)
        if start is not None:
            start = max(0, start - 1)
            end, blanks = start, 0
            while end < len(full) and blanks < 2 and (end - start) < 44:
                end += 1
                blanks = blanks + 1 if not full[end - 1].strip() else 0
            out.append("<h2>Generated C header</h2>")
            out.append(
                f"<p>What <code>regforge gen {esc(pn)}</code> writes for "
                f"<code>{esc(example.name)}</code>:</p>"
            )
            out.append(f"<pre><code>{esc(chr(10).join(full[start:end]).rstrip())}</code></pre>")

    # comparisons involving this part
    comps = [pair for pair in COMPARE_PAIRS if pn in pair]
    if comps:
        out.append("<h2>Compared with</h2><ul>")
        for a, b in comps:
            other = b if a == pn else a
            out.append(
                f'<li><a href="../compare/{slug(a)}-vs-{slug(b)}.html">'
                f"{esc(pn)} vs {esc(other)}</a></li>"
            )
        out.append("</ul>")

    if related:
        out.append("<h2>Related parts</h2>")
        out.append('<div class="grid">')
        for o in related:
            od = o.device
            out.append(
                f'<a class="card" href="{slug(od.part_number)}.html">'
                f'<div class="pn">{esc(od.part_number)}</div>'
                f'<div class="mf">{esc(od.manufacturer)}</div>'
                f'<div class="st">{len(od.registers)} registers</div></a>'
            )
        out.append("</div>")

    out.append("<h2>Source</h2>")
    how = "machine-extracted" if p.extraction_model else "hand-transcribed"
    out.append(
        f"<p>Transcribed from <strong>{esc(p.source_filename or 'unknown')}</strong> ({how}). "
        + (esc(p.notes) if p.notes else "")
        + "</p>"
    )
    out.append(
        f'<p><a href="{GITHUB}/blob/main/corpus/{slug(d.manufacturer)}/{slug(pn)}.json">Raw JSON</a> '
        f'&middot; <a href="{GITHUB}/issues/new?title=Correction%3A+{esc(pn)}">Report an error</a></p>'
    )

    jsonld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": f"{pn} register map",
        "about": {
            "@type": "Product",
            "name": pn,
            "manufacturer": {"@type": "Organization", "name": d.manufacturer},
        },
        "description": desc,
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
        "isAccessibleForFree": True,
    }
    return page(
        title, desc, "\n".join(out),
        canonical=f"parts/{slug(pn)}.html", depth=1, active="index.html", jsonld=jsonld,
    )


# ---------------------------------------------------------------------------
# I2C address map
# ---------------------------------------------------------------------------

def build_address_index(records) -> dict[int, list[str]]:
    idx: dict[int, list[str]] = {}
    for r in records:
        for a in r.device.i2c_addresses:
            idx.setdefault(a, []).append(r.device.part_number)
    for a in idx:
        idx[a] = sorted(set(idx[a]))
    return idx


def render_i2c(records) -> str:
    idx = build_address_index(records)
    clashes = {a: ps for a, ps in idx.items() if len(ps) > 1}

    title = "I²C address map — which chips collide on which address | RegForge"
    desc = (
        "Every 7-bit I²C address from 0x08 to 0x77, showing which common parts claim it "
        "and which addresses have conflicts. Find out before you wire the board."
    )

    out = [
        "<h1>I²C address map</h1>",
        '<p class="lede">Two devices on one address is the classic I²C bring-up failure. '
        "Here is every address these parts claim, and where they collide.</p>",
        '<div class="meta">'
        f'<span class="chip">{len(idx)} addresses in use</span>'
        f'<span class="chip danger">{len(clashes)} with conflicts</span>'
        f'<span class="chip">{len(records)} parts</span>'
        "</div>",
    ]

    # Conflicts are reported per pair of parts, not per address. A part with 64
    # strappable addresses technically "conflicts" with everything in its range,
    # which is true and useless. What a person actually needs to know is whether
    # two specific chips can share a bus -- and the only case where they truly
    # cannot is when both are fixed to the same single address.
    addr_of = {r.device.part_number: set(r.device.i2c_addresses) for r in records if r.device.i2c_addresses}
    names = sorted(addr_of)
    impossible, resolvable = [], []
    for i, pa in enumerate(names):
        for pb in names[i + 1:]:
            shared = addr_of[pa] & addr_of[pb]
            if not shared:
                continue
            # They can coexist iff the union offers at least two distinct addresses.
            if len(addr_of[pa] | addr_of[pb]) < 2:
                impossible.append((pa, pb, shared))
            else:
                resolvable.append((pa, pb, shared))

    def link(p):
        return f'<a href="parts/{slug(p)}.html">{esc(p)}</a>'

    if impossible:
        out.append("<h2>Cannot share a bus, ever</h2>")
        out.append(
            "<p>Both parts are fixed to the same single address with no strap pin. No wiring "
            "change helps: you need an I²C multiplexer such as a TCA9548A, or a second bus.</p>"
        )
        out.append('<div class="tablewrap"><table><thead><tr>'
                   '<th>Pair</th><th class="mono">Address</th><th>Only way out</th>'
                   "</tr></thead><tbody>")
        for pa, pb, shared in impossible:
            out.append(
                f"<tr><td>{link(pa)} + {link(pb)}</td>"
                f'<td class="mono">' + ", ".join(f"0x{a:02X}" for a in sorted(shared)) + "</td>"
                "<td>I²C multiplexer, or put one on a second bus</td></tr>"
            )
        out.append("</tbody></table></div>")

    if resolvable:
        out.append("<h2>Collide by default, fixable by re-strapping</h2>")
        out.append(
            "<p>These overlap on their default addresses, but at least one has an alternate. "
            "Tie the address pin the other way and they coexist fine.</p>"
        )
        out.append("<details><summary>"
                   f"{len(resolvable)} pairs</summary><div class='inner'>")
        out.append('<div class="tablewrap"><table><thead><tr>'
                   '<th>Pair</th><th class="mono">Shared</th><th class="mono">Alternates available</th>'
                   "</tr></thead><tbody>")
        for pa, pb, shared in resolvable:
            free_a = len(addr_of[pa]) - len(shared)
            free_b = len(addr_of[pb]) - len(shared)
            out.append(
                f"<tr><td>{link(pa)} + {link(pb)}</td>"
                f'<td class="mono">' + ", ".join(f"0x{a:02X}" for a in sorted(shared)[:4])
                + ("&hellip;" if len(shared) > 4 else "") + "</td>"
                f'<td class="mono">{esc(pa)}: {free_a} &middot; {esc(pb)}: {free_b}</td></tr>'
            )
        out.append("</tbody></table></div></div></details>")

    out.append("<h2>Full map, 0x08 – 0x77</h2>")
    out.append(
        '<p class="muted">Addresses below 0x08 and above 0x77 are reserved by the I²C '
        "specification and are not usable by devices.</p>"
    )
    out.append('<div class="addrmap">')
    for a in range(0x08, 0x78):
        parts = idx.get(a, [])
        cls = "addr"
        if len(parts) > 1:
            cls += " clash"
        elif parts:
            cls += " used"
        links = "".join(
            f'<a href="parts/{slug(p)}.html">{esc(p)}</a>' for p in parts
        ) or '<span class="muted">free</span>'
        out.append(f'<div class="{cls}" id="x{a:02x}"><div class="hx">0x{a:02X}</div>'
                   f'<div class="pl">{links}</div></div>')
    out.append("</div>")

    out.append(
        '<div class="note"><strong>7-bit vs 8-bit addresses.</strong> Datasheets sometimes print '
        "the address already shifted left by one, with the read/write bit included &mdash; so the "
        "same part appears as 0x76 in one document and 0xEC in another. Everything on this page "
        "is 7-bit, which is what almost every driver API expects. If your address looks twice as "
        "big as it should, that is why.</div>"
    )

    jsonld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "I²C address map",
        "description": desc,
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
        "isAccessibleForFree": True,
    }
    return page(title, desc, "\n".join(out),
                canonical="i2c-addresses.html", active="i2c-addresses.html", jsonld=jsonld)


# ---------------------------------------------------------------------------
# comparison pages
# ---------------------------------------------------------------------------

def render_compare(a_rec: DeviceRecord, b_rec: DeviceRecord) -> str:
    a, b = a_rec.device, b_rec.device
    an, bn = a.part_number, b.part_number

    title = f"{an} vs {bn} — register-level differences | RegForge"
    desc = (
        f"Side-by-side comparison of the {an} and {bn} register maps: which registers exist "
        f"on each, where addresses and reset values differ, and whether they can share an I²C bus."
    )

    a_regs = {r.name: r for r in a.registers}
    b_regs = {r.name: r for r in b.registers}
    only_a = sorted(set(a_regs) - set(b_regs))
    only_b = sorted(set(b_regs) - set(a_regs))
    common = sorted(set(a_regs) & set(b_regs))

    diffs = []
    for n in common:
        ra, rb = a_regs[n], b_regs[n]
        if (ra.address, ra.reset_value, ra.size_bits) != (rb.address, rb.reset_value, rb.size_bits):
            diffs.append((n, ra, rb))

    shared_addr = sorted(set(a.i2c_addresses) & set(b.i2c_addresses))

    out = [
        f'<p class="crumb"><a href="index.html">Comparisons</a> / {esc(an)} vs {esc(bn)}</p>',
        f"<h1>{esc(an)} vs {esc(bn)}</h1>",
        '<p class="lede">Register-level differences, generated from both maps.</p>',
    ]

    if shared_addr:
        out.append(
            '<div class="note danger"><strong>They cannot share an I²C bus by default.</strong> '
            "Both answer on " + ", ".join(f"<code>0x{x:02X}</code>" for x in shared_addr) + ". "
            "Re-strap one, use a multiplexer, or put them on separate buses.</div>"
        )

    out.append('<div class="tablewrap"><table><thead><tr><th></th>'
               f'<th class="mono">{esc(an)}</th><th class="mono">{esc(bn)}</th></tr></thead><tbody>')
    rows = [
        ("Manufacturer", esc(a.manufacturer), esc(b.manufacturer)),
        ("What it is", esc(a.description or ""), esc(b.description or "")),
        ("Registers", str(len(a.registers)), str(len(b.registers))),
        ("Buses", ", ".join(x.value.upper() for x in a.buses), ", ".join(x.value.upper() for x in b.buses)),
        ("I²C addresses",
         ", ".join(f"0x{x:02X}" for x in a.i2c_addresses) or "&mdash;",
         ", ".join(f"0x{x:02X}" for x in b.i2c_addresses) or "&mdash;"),
        ("Shared registers", str(len(common)), str(len(common))),
        ("Unique registers", str(len(only_a)), str(len(only_b))),
    ]
    for label, av, bv in rows:
        out.append(f"<tr><th>{label}</th><td>{av}</td><td>{bv}</td></tr>")
    out.append("</tbody></table></div>")

    if diffs:
        out.append("<h2>Same name, different behaviour</h2>")
        out.append(
            "<p>These registers exist on both parts but are not interchangeable. This is where "
            "a driver ported between them breaks quietly.</p>"
        )
        out.append('<div class="tablewrap"><table><thead><tr>'
                   f'<th class="mono">Register</th><th class="mono">{esc(an)}</th>'
                   f'<th class="mono">{esc(bn)}</th></tr></thead><tbody>')
        for n, ra, rb in diffs:
            def cell(r, dev):
                return (f"{hexv(r.address, dev.register_address_bits)} &middot; {r.size_bits}-bit"
                        f" &middot; reset {hexv(r.reset_value, r.size_bits)}")
            out.append(f'<tr><td class="mono">{esc(n)}</td>'
                       f"<td>{cell(ra, a)}</td><td>{cell(rb, b)}</td></tr>")
        out.append("</tbody></table></div>")

    for label, names, src_dev, href in (
        (f"Only on the {an}", only_a, a, slug(an)),
        (f"Only on the {bn}", only_b, b, slug(bn)),
    ):
        if not names:
            continue
        regs = a_regs if src_dev is a else b_regs
        out.append(f"<h2>{esc(label)}</h2>")
        out.append('<div class="tablewrap"><table><thead><tr>'
                   '<th class="mono">Addr</th><th class="mono">Register</th>'
                   "<th>Description</th></tr></thead><tbody>")
        for n in names:
            r = regs[n]
            out.append(f'<tr><td class="mono">{hexv(r.address, src_dev.register_address_bits)}</td>'
                       f'<td class="mono">{esc(n)}</td><td>{esc(r.description or "")}</td></tr>')
        out.append("</tbody></table></div>")
        out.append(f'<p><a href="../parts/{href}.html">Full {esc(src_dev.part_number)} register map</a></p>')

    out.append("<h2>Get either as C</h2>")
    out.append(f"<pre><code>regforge gen {esc(an)} --out ./src --driver --tests\n"
               f"regforge gen {esc(bn)} --out ./src --driver --tests</code></pre>")

    jsonld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": f"{an} vs {bn}",
        "description": desc,
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
    }
    return page(title, desc, "\n".join(out),
                canonical=f"compare/{slug(an)}-vs-{slug(bn)}.html",
                depth=1, active="compare/index.html", jsonld=jsonld)


def render_compare_index(pairs) -> str:
    title = "Part comparisons — register-level differences | RegForge"
    desc = "Side-by-side register map comparisons of commonly confused embedded parts."
    out = [
        "<h1>Comparisons</h1>",
        '<p class="lede">Parts that look interchangeable and are not. Each page is generated '
        "from both register maps.</p>",
        '<div class="grid">',
    ]
    for a, b in pairs:
        out.append(
            f'<a class="card" href="{slug(a)}-vs-{slug(b)}.html">'
            f'<div class="pn">{esc(a)} vs {esc(b)}</div>'
            f'<div class="st">register-level diff</div></a>'
        )
    out.append("</div>")
    return page(title, desc, "\n".join(out),
                canonical="compare/index.html", depth=1, active="compare/index.html")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def build_search_index(records) -> list[dict]:
    items = []
    for rec in records:
        d = rec.device
        u = f"parts/{slug(d.part_number)}.html"
        items.append({
            "k": "part", "n": d.part_number, "u": u,
            "d": f"{d.manufacturer} — {d.description or ''}",
        })
        for r in d.registers:
            items.append({
                "k": "register", "n": r.name, "u": u,
                "d": f"{d.part_number} @ 0x{r.address:02X} — {r.description or ''}",
                "a": f"0x{r.address:02X}",
            })
            for f in r.fields:
                items.append({
                    "k": "field", "n": f.name, "u": u,
                    "d": f"{d.part_number} {r.name}{bit_span(f)} — {f.description or ''}",
                })
    return items


SEARCH_JS = """
<script>
(function(){
  var q=document.getElementById('q'),out=document.getElementById('results'),data=[];
  fetch('search-index.json').then(function(r){return r.json()}).then(function(j){
    data=j; render(q.value);
  });
  function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
  function render(term){
    term=(term||'').trim().toLowerCase();
    if(!term){out.innerHTML='<p class="muted">Type a part, register, field or address.</p>';return}
    var hits=[];
    for(var i=0;i<data.length&&hits.length<80;i++){
      var it=data[i];
      if(it.n.toLowerCase().indexOf(term)>=0||(it.a&&it.a.toLowerCase()===term)){hits.push(it)}
    }
    if(!hits.length){out.innerHTML='<p class="muted">Nothing found for '+esc(term)+'.</p>';return}
    out.innerHTML=hits.map(function(h){
      return '<a class="hit" href="'+h.u+'"><span class="k">'+h.k+'</span> '+
             '<span class="n">'+esc(h.n)+'</span><br><span class="d">'+esc(h.d)+'</span></a>'
    }).join('');
  }
  q.addEventListener('input',function(){render(q.value)});
  var p=new URLSearchParams(location.search).get('q');
  if(p){q.value=p}
  render(q.value);
})();
</script>
"""


def render_search() -> str:
    title = "Search registers, fields and I²C addresses | RegForge"
    desc = ("Search every register, bitfield and address across the corpus. "
            "Find which part has a WHO_AM_I, or what lives at 0xF4.")
    out = [
        "<h1>Search</h1>",
        '<p class="lede">Every part, register and bitfield in the corpus. '
        "Try <code>WHO_AM_I</code>, <code>CTRL</code>, <code>0xF4</code> or <code>MODE</code>.</p>",
        '<div class="searchbox"><input id="q" type="search" autocomplete="off" '
        'placeholder="part, register, field, or 0xNN" autofocus></div>',
        '<div id="results"><p class="muted">Loading…</p></div>',
    ]
    return page(title, desc, "\n".join(out),
                canonical="search.html", active="search.html", scripts=SEARCH_JS)


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------

def render_index(records, clash_count: int) -> str:
    title = "RegForge — register maps, bitfields and C drivers for embedded parts"
    desc = ("Open register maps for common I²C and SPI chips: addresses, bitfields, reset values, "
            "I²C conflict map, and one-command C header generation.")
    total = sum(len(r.device.registers) for r in records)

    out = [
        "<h1>Register maps for I²C and SPI chips</h1>",
        '<p class="lede">Every address, bitfield and reset value &mdash; and the same data '
        "as a C header, in one command.</p>",
        "<pre><code>pip install regforge\nregforge gen BME280 --out ./src --driver --tests</code></pre>",
        '<div class="meta">'
        f'<span class="chip">{len(records)} parts</span>'
        f'<span class="chip">{total} registers</span>'
        '<span class="chip">no API key needed</span>'
        '<span class="chip">Apache-2.0</span>'
        "</div>",
        '<div class="grid">',
        '<a class="card" href="i2c-addresses.html"><div class="pn">I²C address map</div>'
        f'<div class="mf">{clash_count} conflicts found</div>'
        '<div class="st">before you wire the board</div></a>',
        '<a class="card" href="search.html"><div class="pn">Search</div>'
        '<div class="mf">registers, fields, addresses</div>'
        '<div class="st">what has a WHO_AM_I?</div></a>',
        '<a class="card" href="compare/index.html"><div class="pn">Comparisons</div>'
        '<div class="mf">parts people confuse</div>'
        '<div class="st">register-level diffs</div></a>',
        "</div>",
        "<h2>Parts</h2>",
        '<div class="grid">',
    ]
    for rec in sorted(records, key=lambda r: slug(r.device.part_number)):
        d = rec.device
        out.append(
            f'<a class="card" href="parts/{slug(d.part_number)}.html">'
            f'<div class="pn">{esc(d.part_number)}</div>'
            f'<div class="mf">{esc(d.manufacturer)}</div>'
            f'<div class="st">{len(d.registers)} registers &middot; '
            f'{esc(", ".join(b.value.upper() for b in d.buses))}</div></a>'
        )
    out += [
        "</div>",
        "<h2>The problem</h2>",
        "<p>Bringing up a new chip means retyping register tables out of a PDF into a header "
        "by hand. <code>[7:5]</code> means shift 5, width 3. Get it backwards and nothing tells "
        "you &mdash; you find out on a logic analyser, a day later.</p>",
        "<h2>The solution</h2>",
        "<p>Read the map here, or generate it as C. The generated header ships with compile-time "
        "assertions, so a wrong mask is a <strong>build failure naming the field</strong> instead "
        "of a silent hardware bug.</p>",
        "<h2>Missing a part?</h2>",
        "<pre><code>regforge scan datasheet.pdf          # free, shows which pages it will read\n"
        "regforge extract datasheet.pdf --part XYZ</code></pre>",
        f'<p><a href="{GITHUB}/blob/main/CONTRIBUTING.md">Contribute it back</a> and it is free '
        "for everyone after you. Each part gets paid for once.</p>",
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
    return page(title, desc, "\n".join(out), canonical="index.html",
                active="index.html", jsonld=jsonld)


def write_search_index(path, records) -> int:
    items = build_search_index(records)
    path.write_text(json.dumps(items, separators=(",", ":")), encoding="utf-8")
    return len(items)
