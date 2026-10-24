"""Build cookingbrilliant.com into dist/.

Reads data/*.json and content/*.md, renders templates/ with Jinja2, copies static/.
Every number shown on the site comes from data/usda_portions.json, data/oven.json or
data/measures.json. The only arithmetic is scaling a sourced weight (half a cup is
half the cup weight) and converting between cup sizes, and the pages say so.

    python build.py            # build into dist/
    python build.py --serve    # build, then serve dist/ on http://localhost:8000
"""
import json
import math
import shutil
import sys
from datetime import date
from fractions import Fraction
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
TODAY = date.today().isoformat()


def load(name):
    return json.loads((ROOT / name).read_text())


SITE = load("site.json")
MEASURES = load("data/measures.json")
OVEN = load("data/oven.json")
USDA = load("data/usda_portions.json")
INGREDIENTS = load("data/ingredients.json")

ML = {k: v["ml"] for k, v in MEASURES["units"].items()}


# ---------------------------------------------------------------- numbers
def half_up(x, places=0):
    """Round half up, matching JavaScript's Math.round so pages and tools agree."""
    f = 10 ** places
    return math.floor(x * f + 0.5) / f


def fmt_g(x):
    """Round a weight for display: one decimal under 10g, whole grams above."""
    if x < 10:
        return f"{half_up(x, 1):g}"
    return f"{int(half_up(x)):,}"


def fmt_ml(x):
    return f"{int(half_up(x)):,}" if x >= 10 else f"{half_up(x, 1):g}"


FRACTION_WORDS = {
    Fraction(1, 8): "⅛", Fraction(1, 4): "¼", Fraction(1, 3): "⅓", Fraction(1, 2): "½",
    Fraction(2, 3): "⅔", Fraction(3, 4): "¾",
}


def fmt_qty(q):
    q = Fraction(q).limit_denominator(8)
    whole, part = divmod(q, 1)
    s = str(whole) if whole else ""
    if part:
        s += FRACTION_WORDS.get(part, f"{part.numerator}/{part.denominator}")
    return s or "0"


def portion(ndb, measure):
    """Grams for ONE unit of a USDA household measure (USDA sometimes lists 2 tbsp or 0.25 cup)."""
    for p in USDA["foods"][ndb]["portions"]:
        if p["measure"] == measure:
            return p["grams"] / p["amount"], p
    raise KeyError(f"{ndb}: no USDA measure {measure!r}")


def resolve(ing):
    """Work out grams per US cup / tbsp / tsp / stick, recording where each came from."""
    ndb = ing["ndb"]
    u = {}
    if "cup" in ing:
        g, p = portion(ndb, ing["cup"])
        u["cup"] = {"g": g, "how": "usda", "usda": p}
    if "tbsp" in ing:
        g, p = portion(ndb, ing["tbsp"])
        u["tbsp"] = {"g": g, "how": "usda", "usda": p}
    elif "cup" in u:
        u["tbsp"] = {"g": u["cup"]["g"] / 16, "how": "calc", "from": "cup", "factor": "1/16"}
    if "tsp" in ing:
        g, p = portion(ndb, ing["tsp"])
        u["tsp"] = {"g": g, "how": "usda", "usda": p}
    elif "tbsp" in u:
        u["tsp"] = {"g": u["tbsp"]["g"] / 3, "how": "calc", "from": "tbsp", "factor": "1/3"}
    if "stick" in ing:
        g, p = portion(ndb, ing["stick"])
        u["stick"] = {"g": g, "how": "usda", "usda": p}
    if "cup" in u:
        u["metric_cup"] = {"g": u["cup"]["g"] * ML["metric_cup"] / ML["us_cup"], "how": "calc"}
    if "tbsp" in u:
        u["au_tbsp"] = {"g": u["tbsp"]["g"] * ML["au_tbsp"] / ML["us_tbsp"], "how": "calc"}
    alts = []
    for a in ing.get("alt", []):
        g, p = portion(ndb, a["measure"])
        alts.append({"label": a["label"], "g": g, "usda": p})
    return u, alts


# Quantity pages: one per common search phrasing. Kept deliberately small so each
# page earns its place rather than being a near-copy of the ingredient page.
QUANTITY_PAGES = [
    ("1-cup", "cup", Fraction(1), "1 cup"),
    ("half-a-cup", "cup", Fraction(1, 2), "half a cup"),
    ("quarter-cup", "cup", Fraction(1, 4), "a quarter cup"),
    ("1-tablespoon", "tbsp", Fraction(1), "1 tablespoon"),
    ("1-stick", "stick", Fraction(1), "1 stick"),
]

CUP_ROWS = [Fraction(1, 4), Fraction(1, 3), Fraction(1, 2), Fraction(2, 3), Fraction(3, 4), Fraction(1), Fraction(2)]


def build_ingredient(ing):
    units, alts = resolve(ing)
    usda_food = USDA["foods"][ing["ndb"]]
    rows = []
    if "cup" in units:
        for q in CUP_ROWS:
            g = units["cup"]["g"] * q
            mg = units["metric_cup"]["g"] * q
            ml = ML["us_cup"] * q
            word = "cup" if q <= 1 else "cups"
            rows.append({"label": f"{fmt_qty(q)} {word}", "g": fmt_g(g), "metric_g": fmt_g(mg),
                         "ml": fmt_ml(ml) if ing.get("liquid") else None})
    spoons = []
    if "tbsp" in units:
        spoons.append({"label": "1 tablespoon", "g": fmt_g(units["tbsp"]["g"]),
                       "au": fmt_g(units["au_tbsp"]["g"]), "how": units["tbsp"]["how"]})
    if "tsp" in units:
        spoons.append({"label": "1 teaspoon", "g": fmt_g(units["tsp"]["g"]), "au": None,
                       "how": units["tsp"]["how"]})
    if "stick" in units:
        spoons.append({"label": "1 stick", "g": fmt_g(units["stick"]["g"]), "au": None, "how": "usda"})

    headline_unit = "cup" if "cup" in units else ("tbsp" if "tbsp" in units else "tsp")
    headline = {
        "cup": ("1 cup", units.get("cup")),
        "tbsp": ("1 tablespoon", units.get("tbsp")),
        "tsp": ("1 teaspoon", units.get("tsp")),
    }[headline_unit]
    return {
        **ing,
        "liquid": bool(ing.get("liquid")),
        "note": ing.get("note"),
        "units": units,
        "alts": [{"label": a["label"], "g": fmt_g(a["g"])} for a in alts],
        "rows": rows,
        "spoons": spoons,
        "headline_label": headline[0],
        "headline_g": fmt_g(headline[1]["g"]),
        "metric_cup_g": fmt_g(units["metric_cup"]["g"]) if "metric_cup" in units else None,
        "usda_description": usda_food["description"],
        "usda_portions": usda_food["portions"],
        "url": f"/convert/{ing['slug']}/",
    }


def quantity_pages(item):
    pages = []
    for slug, unit, q, phrase in QUANTITY_PAGES:
        if unit not in item["units"]:
            continue
        u = item["units"][unit]
        g = u["g"] * q
        page = {
            "slug": slug, "phrase": phrase, "unit": unit, "q": q, "g": fmt_g(g),
            "oz": f"{half_up(g / 28.349523125, 1):g}",
            "how": u["how"],
            "url": f"{item['url']}{slug}-to-grams/",
        }
        if unit == "cup":
            page["metric_g"] = fmt_g(item["units"]["metric_cup"]["g"] * q)
            page["ml"] = fmt_ml(ML["us_cup"] * q)
        if unit == "tbsp":
            page["metric_g"] = fmt_g(item["units"]["au_tbsp"]["g"])
        pages.append(page)
    return pages


# ---------------------------------------------------------------- render
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True,
                  trim_blocks=True, lstrip_blocks=True)
env.globals.update(site=SITE, today=TODAY, measures=MEASURES, usda_meta=USDA)


def write(url, template, **ctx):
    path = DIST / url.lstrip("/")
    if url.endswith("/"):
        path = path / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    html = env.get_template(template).render(url=url, canonical=SITE["base_url"] + url, **ctx)
    path.write_text(html)
    return url


def md_page(name):
    text = (ROOT / "content" / f"{name}.md").read_text()
    meta, _, body = text.partition("\n---\n")
    fields = dict(line.split(": ", 1) for line in meta.strip().splitlines())
    body = body.replace("{{contact_email}}", SITE["contact_email"]).replace("{{owner}}", SITE["owner"])
    return fields, markdown.markdown(body, extensions=["tables"])


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", DIST)
    urls = []

    items = [build_ingredient(i) for i in INGREDIENTS]
    by_group = {}
    for it in items:
        by_group.setdefault(it["group"], []).append(it)

    # Data for the browser converter: grams per unit only, no copy.
    conv = [{"s": it["slug"], "n": it["name"], "us": it["us_name"],
             "u": {k: round(v["g"], 3) for k, v in it["units"].items() if k in ("cup", "tbsp", "tsp", "stick")},
             "l": bool(it.get("liquid"))} for it in items]
    (DIST / "js" / "ingredients.json").write_text(json.dumps(conv, separators=(",", ":")))

    for it in items:
        qp = quantity_pages(it)
        related = [o for o in by_group[it["group"]] if o["slug"] != it["slug"]][:6]
        urls.append(write(it["url"], "ingredient.html", item=it, qpages=qp, related=related,
                          title=f"{it['name']}: cups to grams", page_kind="ingredient"))
        for p in qp:
            others = [o for o in qp if o["slug"] != p["slug"]]
            urls.append(write(p["url"], "quantity.html", item=it, p=p, others=others,
                              title=f"{p['phrase'].capitalize()} of {it['name'].lower()} in grams",
                              page_kind="quantity"))

    urls.append(write("/", "home.html", groups=by_group, title="Kitchen conversions that get to the point", page_kind="home"))
    urls.append(write("/convert/", "converter.html", groups=by_group, title="Cups to grams converter", page_kind="tool"))
    urls.append(write("/oven-temperatures/", "oven.html", oven=OVEN, title="Oven temperature converter: °C, fan, °F and gas mark", page_kind="tool"))
    urls.append(write("/recipe-scaler/", "scaler.html", title="Recipe scaler", page_kind="tool"))
    for name in ("about", "privacy", "contact", "sources"):
        fields, body = md_page(name)
        urls.append(write(f"/{name}/", "page.html", body=body, title=fields["title"],
                          description=fields["description"], page_kind="page", items=items))
    write("/404.html", "404.html", title="Page not found", page_kind="page")

    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sitemap += [f"<url><loc>{SITE['base_url']}{u}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls]
    sitemap.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sitemap) + "\n")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE['base_url']}/sitemap.xml\n")
    if SITE.get("adsense_client"):
        pub = SITE["adsense_client"].replace("ca-", "")
        (DIST / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
    print(f"Built {len(urls)} pages into {DIST}")


if __name__ == "__main__":
    main()
    if "--serve" in sys.argv:
        import http.server, functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        print("Serving on http://localhost:8000")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()
