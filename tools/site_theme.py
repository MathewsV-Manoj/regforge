"""Shared page shell, styling and small helpers for the generated site."""

from __future__ import annotations

import html
import json

GITHUB = "https://github.com/MathewsV-Manoj/regforge"
BASE_URL = "https://mathewsv-manoj.github.io/regforge/"
SITE_NAME = "RegForge"

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#fbfaf8; --surface:#fff; --border:#e5e1da; --text:#1c1a17;
  --muted:#6b6560; --accent:#b4532a; --accent-soft:#fdf0e9;
  --code-bg:#f5f2ee; --ok:#2f6f4f; --ok-soft:#eaf3ee;
  --warn:#8a6d1f; --warn-soft:#fbf3dd; --danger:#a33328; --danger-soft:#fbeae8;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#161513; --surface:#1e1d1a; --border:#332f2a; --text:#eae6e0;
    --muted:#9a938b; --accent:#e08a5f; --accent-soft:#2a201a;
    --code-bg:#211f1c; --ok:#6bbd91; --ok-soft:#1b2a22;
    --warn:#d6b25f; --warn-soft:#2a2418; --danger:#e8806f; --danger-soft:#2e1c19;
  }
}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;overflow-x:hidden}
.wrap{max-width:960px;margin:0 auto;padding:0 16px}
header.site{border-bottom:1px solid var(--border);background:var(--surface);position:sticky;top:0;z-index:20}
header.site .wrap{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:12px 16px}
.brand{font-weight:700;letter-spacing:-.02em;text-decoration:none;color:var(--text);font-size:18px}
.brand span{color:var(--accent)}
header.site nav{margin-left:auto;display:flex;gap:16px;flex-wrap:wrap}
header.site nav a{color:var(--muted);text-decoration:none;font-size:14px;white-space:nowrap}
header.site nav a:hover,header.site nav a.on{color:var(--accent)}
h1{font-size:clamp(25px,5vw,36px);line-height:1.15;letter-spacing:-.03em;margin:26px 0 8px}
h2{font-size:21px;letter-spacing:-.02em;margin:34px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--border)}
h3{font-size:16px;margin:24px 0 8px;font-family:var(--mono);color:var(--accent)}
p{margin:0 0 14px}
a{color:var(--accent)}
.lede{font-size:18px;color:var(--muted);margin-bottom:20px}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 22px}
.chip{font-size:12px;font-family:var(--mono);padding:4px 9px;border-radius:99px;
  background:var(--accent-soft);color:var(--accent);border:1px solid var(--border);white-space:nowrap}
.chip.ok{color:var(--ok);background:var(--ok-soft)}
.chip.warn{color:var(--warn);background:var(--warn-soft)}
.chip.danger{color:var(--danger);background:var(--danger-soft)}
pre{background:var(--code-bg);border:1px solid var(--border);border-radius:8px;padding:14px;
  overflow-x:auto;font-family:var(--mono);font-size:13px;line-height:1.5;margin:0 0 16px}
code{font-family:var(--mono);font-size:.9em;background:var(--code-bg);padding:1px 5px;border-radius:4px}
pre code{background:none;padding:0;font-size:inherit}
.tablewrap{overflow-x:auto;margin:0 0 18px;border:1px solid var(--border);border-radius:8px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:480px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:none}
td.mono,th.mono{font-family:var(--mono);font-size:13px;white-space:nowrap}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));margin:0 0 24px}
.card{display:block;padding:15px;border:1px solid var(--border);border-radius:10px;background:var(--surface);
  text-decoration:none;color:inherit;transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card .pn{font-family:var(--mono);font-weight:700;color:var(--accent);font-size:15px}
.card .mf{font-size:13px;color:var(--muted);margin-top:2px}
.card .st{font-size:12px;color:var(--muted);margin-top:8px;font-family:var(--mono)}
.note{border-left:3px solid var(--accent);background:var(--accent-soft);padding:12px 14px;
  border-radius:0 8px 8px 0;margin:0 0 20px;font-size:14px}
.note.danger{border-color:var(--danger);background:var(--danger-soft)}
.note.ok{border-color:var(--ok);background:var(--ok-soft)}
details{border:1px solid var(--border);border-radius:8px;background:var(--surface);margin-bottom:8px}
summary{padding:10px 14px;cursor:pointer;font-family:var(--mono);font-size:14px}
summary::marker{color:var(--accent)}
details[open] summary{border-bottom:1px solid var(--border)}
details .inner{padding:12px 14px}
footer.site{border-top:1px solid var(--border);margin-top:52px;padding:22px 0 40px;color:var(--muted);font-size:14px}
footer.site a{color:var(--muted)}
.crumb{font-size:14px;color:var(--muted);margin:18px 0 0}
.crumb a{color:var(--muted);text-decoration:none}
.crumb a:hover{color:var(--accent)}

/* bit layout diagram */
.bitsbox{overflow-x:auto;margin:0 0 14px}
.bits{display:grid;gap:3px;min-width:420px}
.bits .cell{border:1px solid var(--border);border-radius:5px;background:var(--surface);
  padding:6px 4px;text-align:center;font-family:var(--mono);font-size:11px;line-height:1.35;overflow:hidden}
.bits .cell.named{background:var(--accent-soft);border-color:var(--accent)}
.bits .cell .nm{display:block;font-weight:700;color:var(--accent);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bits .cell.unnamed .nm{color:var(--muted);font-weight:400}
.bits .cell .ix{display:block;color:var(--muted);font-size:10px;margin-top:2px}

/* i2c address map */
.addrmap{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:6px;margin:0 0 20px}
.addr{border:1px solid var(--border);border-radius:7px;background:var(--surface);padding:8px;font-size:12px}
.addr.used{border-color:var(--accent);background:var(--accent-soft)}
.addr.clash{border-color:var(--danger);background:var(--danger-soft)}
.addr .hx{font-family:var(--mono);font-weight:700;font-size:13px}
.addr .pl{margin-top:4px;line-height:1.4}
.addr .pl a{text-decoration:none;display:block;font-family:var(--mono);font-size:11px}
.addr.clash .hx{color:var(--danger)}

/* search */
.searchbox{position:relative;margin:0 0 18px}
#q{width:100%;padding:12px 14px;font-size:16px;font-family:var(--mono);color:var(--text);
  background:var(--surface);border:1px solid var(--border);border-radius:9px}
#q:focus{outline:2px solid var(--accent);outline-offset:1px}
#results{margin-top:12px}
.hit{display:block;padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--surface);
  margin-bottom:6px;text-decoration:none;color:inherit;font-size:14px}
.hit:hover{border-color:var(--accent)}
.hit .k{font-family:var(--mono);font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.hit .n{font-family:var(--mono);font-weight:700;color:var(--accent)}
.hit .d{color:var(--muted);font-size:13px}
.muted{color:var(--muted)}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


NAV = [
    ("index.html", "Parts"),
    ("i2c-addresses.html", "I²C addresses"),
    ("compare/index.html", "Compare"),
    ("search.html", "Search"),
]


def page(
    title: str,
    description: str,
    body: str,
    *,
    canonical: str,
    depth: int = 0,
    active: str = "",
    jsonld: dict | None = None,
    scripts: str = "",
) -> str:
    """Render a full page. `depth` is how many directories deep the file sits."""
    up = "../" * depth
    abs_url = BASE_URL + canonical.lstrip("/")
    ld = (
        f'<script type="application/ld+json">{json.dumps(jsonld, separators=(",", ":"))}</script>'
        if jsonld
        else ""
    )
    # Built without backslashes inside the f-string expression: that is a
    # SyntaxError before Python 3.12, and CI runs 3.10.
    nav_items = []
    for href, label in NAV:
        cls = ' class="on"' if href == active else ""
        nav_items.append(f'    <a href="{up}{href}"{cls}>{esc(label)}</a>')
    nav = "\n".join(nav_items)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(abs_url)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(abs_url)}">
<meta name="twitter:card" content="summary">
<style>{CSS}</style>
{ld}
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="{up}index.html">Reg<span>Forge</span></a>
  <nav>
{nav}
    <a href="{GITHUB}">GitHub</a>
  </nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
  <p>{SITE_NAME} &middot; Apache-2.0 &middot; <a href="{GITHUB}">github.com/MathewsV-Manoj/regforge</a></p>
  <p>Register data is transcribed from manufacturer datasheets and is not yet human-verified.
     Always check the official datasheet before relying on it in a design.</p>
</div></footer>
{scripts}
</body>
</html>
"""


def hexv(v, bits: int = 8) -> str:
    if v is None:
        return "&mdash;"
    return f"0x{v:0{max(2, (bits + 3) // 4)}X}"


def bit_span(f) -> str:
    return f"[{f.bit_high}:{f.bit_offset}]" if f.bit_width > 1 else f"[{f.bit_offset}]"


def bit_diagram(reg) -> str:
    """A visual MSB-left bit layout for one register.

    Datasheets draw register layouts this way and tables do not, which is
    exactly why bit offsets get misread. Rendering it makes `[7:5]` obvious
    without anyone having to decode the notation in their head.
    """
    n = reg.size_bits
    if n <= 0 or n > 32:
        return ""

    owner: dict[int, object] = {}
    for f in reg.fields:
        if f.bit_width < 1 or f.bit_offset < 0 or f.bit_high >= n:
            continue
        for b in range(f.bit_offset, f.bit_high + 1):
            owner[b] = f

    cells = []
    bit = n - 1  # MSB first, left to right
    while bit >= 0:
        f = owner.get(bit)
        if f is None:
            cells.append(
                f'<div class="cell unnamed" style="grid-column:span 1">'
                f'<span class="nm">&mdash;</span><span class="ix">{bit}</span></div>'
            )
            bit -= 1
        else:
            span = f.bit_width
            cells.append(
                f'<div class="cell named" style="grid-column:span {span}" title="{esc(f.name)} {bit_span(f)}">'
                f'<span class="nm">{esc(f.name)}</span>'
                f'<span class="ix">{bit_span(f)}</span></div>'
            )
            bit = f.bit_offset - 1

    return (
        f'<div class="bitsbox"><div class="bits" style="grid-template-columns:repeat({n},1fr)">'
        + "".join(cells)
        + "</div></div>"
    )


__all__ = [
    "GITHUB",
    "BASE_URL",
    "SITE_NAME",
    "CSS",
    "esc",
    "page",
    "hexv",
    "bit_span",
    "bit_diagram",
]
