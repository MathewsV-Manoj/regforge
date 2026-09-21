"""Build the static site from the corpus.

The strategic point: embedded engineers do not search for "datasheet to driver
tool". They search for "BME280 register map", "MPU6050 WHO_AM_I address" and
"I2C address 0x68 conflict". The corpus is already the best structured answer
to those queries -- it was just sitting in JSON where no search engine would
ever find it.

Everything here is derived from the corpus, so the site grows automatically as
parts are added and can never drift out of step with what the tool ships.

    python tools/build_site.py             # writes ./site
    python tools/build_site.py --out docs  # or wherever
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from regforge.corpus import Corpus, slug  # noqa: E402

from site_pages import (  # noqa: E402
    COMPARE_PAIRS,
    build_address_index,
    pick_related,
    render_compare,
    render_compare_index,
    render_i2c,
    render_index,
    render_part,
    render_search,
    write_search_index,
)
from site_theme import BASE_URL  # noqa: E402


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

    records = [corpus.load_path(e.path) for e in entries]
    out = Path(args.out)
    (out / "parts").mkdir(parents=True, exist_ok=True)
    (out / "compare").mkdir(parents=True, exist_ok=True)

    addr_index = build_address_index(records)
    clashes = {a: ps for a, ps in addr_index.items() if len(ps) > 1}
    urls: list[str] = ["index.html", "i2c-addresses.html", "search.html", "compare/index.html"]

    # part pages
    for rec in records:
        name = f"parts/{slug(rec.device.part_number)}.html"
        (out / name).write_text(
            render_part(rec, pick_related(rec, records), addr_index), encoding="utf-8"
        )
        urls.append(name)
        print(f"  {name}")

    # comparisons, only for pairs where both parts exist
    by_pn = {r.device.part_number: r for r in records}
    pairs = [(a, b) for a, b in COMPARE_PAIRS if a in by_pn and b in by_pn]
    for a, b in pairs:
        name = f"compare/{slug(a)}-vs-{slug(b)}.html"
        (out / name).write_text(render_compare(by_pn[a], by_pn[b]), encoding="utf-8")
        urls.append(name)
        print(f"  {name}")

    (out / "compare" / "index.html").write_text(render_compare_index(pairs), encoding="utf-8")
    (out / "i2c-addresses.html").write_text(render_i2c(records), encoding="utf-8")
    (out / "search.html").write_text(render_search(), encoding="utf-8")
    (out / "index.html").write_text(render_index(records, len(clashes)), encoding="utf-8")
    n_items = write_search_index(out / "search-index.json", records)
    print("  index.html / i2c-addresses.html / search.html / compare/index.html")

    today = date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"<url><loc>{BASE_URL}{u}</loc><lastmod>{today}</lastmod></url>")
    sm.append("</urlset>")
    (out / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}sitemap.xml\n", encoding="utf-8"
    )
    (out / ".nojekyll").write_text("", encoding="utf-8")

    print(
        f"\n{len(records)} parts, {len(pairs)} comparisons, {len(clashes)} address conflicts, "
        f"{n_items} search entries, {len(urls)} URLs -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
