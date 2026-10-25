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
ROASTS = load("data/roasts.json")
XMAS = load("data/christmas.json")
TG = load("data/thanksgiving.json")
OTHER = load("data/other_sources.json")
YE = load("data/yeast_eggs.json")

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
    rows = [p for p in USDA["foods"][ndb]["portions"] if p["measure"] == measure]
    if not rows:
        raise KeyError(f"{ndb}: no USDA measure {measure!r}")
    # USDA sometimes lists the same measure at several amounts (1 cup and 1/4 cup).
    # Use the one closest to a single unit, so the figure is one USDA measured directly.
    p = min(rows, key=lambda r: abs(r["amount"] - 1))
    return p["grams"] / p["amount"], p


def resolve_other(ing):
    """Ingredients from a non-USDA source: a quoted weight per US cup, or a density."""
    f = OTHER["foods"][ing["src"]]
    u = {}
    if "cup_g" in f:
        u["cup"] = {"g": f["cup_g"], "how": "source"}
        u["tbsp"] = {"g": f["cup_g"] / 16, "how": "calc", "from": "cup", "factor": "1/16"}
    else:
        u["cup"] = {"g": f["density"] * ML["us_cup"], "how": "density"}
        u["tbsp"] = {"g": f["density"] * ML["us_tbsp"], "how": "density"}
    u["tsp"] = {"g": u["tbsp"]["g"] / 3, "how": "calc", "from": "tbsp", "factor": "1/3"}
    u["metric_cup"] = {"g": u["cup"]["g"] * ML["metric_cup"] / ML["us_cup"], "how": "calc"}
    u["au_tbsp"] = {"g": u["tbsp"]["g"] * ML["au_tbsp"] / ML["us_tbsp"], "how": "calc"}
    return u, []


def resolve(ing):
    """Work out grams per US cup / tbsp / tsp / stick, recording where each came from."""
    if "src" in ing:
        return resolve_other(ing)
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
    if "src" in ing:
        f = OTHER["foods"][ing["src"]]
        usda_food = {"description": None, "portions": []}
        other = {**f, "source_info": OTHER["sources"][f["source"]]}
    else:
        usda_food = USDA["foods"][ing["ndb"]]
        other = None
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
        "other": other,
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


# ---------------------------------------------------------------- grams to cups
# Must match CB.kitchen() in static/js/common.js. Tested against each other.
CUP_FRACS = [(0, ""), (1/4, "¼"), (1/3, "⅓"), (1/2, "½"), (2/3, "⅔"), (3/4, "¾")]
TOL = 1 / 32  # half a tablespoon, in cups


def kitchen(g, cup_g, tbsp_g):
    """A weight as cups plus tablespoons, the way a recipe would write it."""
    cups = g / cup_g
    if cups < 0.25 - TOL:
        t = g / tbsp_g
        h = math.floor(t * 2 + 0.5) / 2
        if h < 0.5:
            return "less than ½ tbsp"
        whole = int(h)
        txt = (str(whole) if whole else "") + ("½" if h - whole else "")
        return f"{txt} tbsp"
    whole = math.floor(cups + TOL)
    rem = cups - whole
    frac, sym = 0, ""
    for f, s in CUP_FRACS:
        if f <= rem + TOL:
            frac, sym = f, s
    left = int(math.floor((rem - frac) * 16 + 0.5))
    if left >= 4:  # rounds up to the next quarter cup
        return kitchen(cup_g * (whole + frac + 0.25), cup_g, tbsp_g)
    base = (str(whole) if whole else "") + sym
    word = "cup" if (whole == 0 or (whole == 1 and not frac)) else "cups"
    out = f"{base} {word}"
    if left > 0:
        out += f" + {left} tbsp"
    return out


REVERSE_WEIGHTS = [50, 100, 125, 150, 200, 250, 300, 500]
REVERSE_PAGES = [100, 200, 250]


def reverse_rows(item):
    u = item["units"]
    if "cup" not in u:
        return []
    return [{"g": w, "measure": kitchen(w, u["cup"]["g"], u["tbsp"]["g"]),
             "cups": f"{w / u['cup']['g']:.2f}"} for w in REVERSE_WEIGHTS]


def reverse_pages(item):
    u = item["units"]
    if "cup" not in u:
        return []
    out = []
    for w in REVERSE_PAGES:
        out.append({"g": w, "measure": kitchen(w, u["cup"]["g"], u["tbsp"]["g"]),
                    "cups": f"{w / u['cup']['g']:.2f}",
                    "metric_cups": f"{w / u['metric_cup']['g']:.2f}",
                    "tbsp": f"{half_up(w / u['tbsp']['g']):g}",
                    "url": f"{item['url']}{w}g-to-cups/"})
    return out


# ---------------------------------------------------------------- cake tins
# Pure geometry: scale a recipe by the ratio of tin areas, assuming the same depth.
# Must match static/js/tin.js. Sizes in cm.
TIN_ROUND = [15, 18, 20, 23, 25, 28]
TIN_SQUARE = [15, 18, 20, 23, 25]


def tin_area(shape, a, b=None):
    if shape == "round":
        return math.pi * (a / 2) ** 2
    if shape == "square":
        return a * a
    return a * b


def tin_label(shape, a, b=None):
    if shape == "rect":
        return f"{a:g} x {b:g}cm rectangular"
    return f"{a:g}cm {shape}"


def tin_inches(cm):
    return f"{half_up(cm / 2.54):g}in"


def tin_pairs():
    """Popular conversions: neighbouring round sizes, round to square of similar size, neighbouring squares."""
    pairs = []
    for i, a in enumerate(TIN_ROUND):
        for b in TIN_ROUND[max(0, i - 2):i + 3]:
            if a != b:
                pairs.append((("round", a), ("round", b)))
        for b in TIN_SQUARE:
            if abs(a - b) <= 3:
                pairs.append((("round", a), ("square", b)))
                pairs.append((("square", b), ("round", a)))
    for i, a in enumerate(TIN_SQUARE):
        for b in TIN_SQUARE[max(0, i - 1):i + 2]:
            if a != b:
                pairs.append((("square", a), ("square", b)))
    seen, out = set(), []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def tin_page(frm, to):
    fa, ta = tin_area(*frm), tin_area(*to)
    k = ta / fa
    pct = round((k - 1) * 100)
    return {
        "from": frm, "to": to, "k": f"{k:.2f}", "kf": k,
        "from_label": tin_label(*frm), "to_label": tin_label(*to),
        "from_in": tin_inches(frm[1]), "to_in": tin_inches(to[1]),
        "from_area": f"{half_up(fa, 2):g}", "to_area": f"{half_up(ta, 2):g}",
        "change": (f"{pct}% more" if pct > 0 else f"{-pct}% less") if pct else "the same",
        "examples": [{"before": "100g", "after": f"{fmt_g(100 * k)}g"},
                     {"before": "250g", "after": f"{fmt_g(250 * k)}g"},
                     {"before": "3 eggs", "after": f"{half_up(3 * k, 1):g} eggs"}],
        "url": f"/cake-tin-converter/{frm[1]}cm-{frm[0]}-to-{to[1]}cm-{to[0]}/",
    }


def tin_equivalents():
    rows = []
    for d in TIN_ROUND:
        side = math.sqrt(tin_area("round", d))
        nearest = min(TIN_SQUARE + [28], key=lambda s: abs(s - side))
        rows.append({"round": d, "round_in": tin_inches(d), "side": f"{half_up(side, 1):g}", "nearest": nearest})
    return rows


# ---------------------------------------------------------------- yeast and eggs
OZ_G = 28.349523125


def yeast_dry(fresh_g):
    """Dried yeast for a weight of fresh, under each maker's ratio."""
    return [{"label": r["label"], "g": fmt_g(fresh_g * r["dry_per_fresh"]),
             "tsp": fmt_qty(Fraction(half_up(fresh_g * r["dry_per_fresh"] / YE["yeast"]["packet_g"] * YE["yeast"]["packet_tsp"] * 4) / 4).limit_denominator(4))}
            for r in YE["yeast"]["ratios"]]


def yeast_fresh(dry_g):
    return [{"label": r["label"], "g": fmt_g(dry_g / r["dry_per_fresh"])} for r in YE["yeast"]["ratios"]]


def yeast_pages():
    y = YE["yeast"]
    pages = []
    for g in y["fresh_pages"]:
        pages.append({"kind": "fresh", "g": g, "results": yeast_dry(g),
                      "url": f"/yeast-converter/{g}g-fresh-yeast-to-dried/",
                      "title": f"{g}g fresh yeast in dried yeast"})
    for g in y["dry_pages"]:
        pages.append({"kind": "dry", "g": g, "results": yeast_fresh(g),
                      "url": f"/yeast-converter/{g}g-dried-yeast-to-fresh/",
                      "title": f"{g}g dried yeast in fresh yeast"})
    return pages


def egg_rows():
    shelled = {p["measure"]: p["grams"] for p in USDA["foods"]["01123"]["portions"]}
    uk = YE["eggs"]["uk"]
    rows = []
    for e in YE["eggs"]["us"]:
        per_egg = e["oz_dozen"] * OZ_G / 12
        band = next(b for b in uk if per_egg >= b["min"] and (b["max"] is None or per_egg < b["max"]))
        rows.append({"size": e["size"], "oz_dozen": e["oz_dozen"], "per_egg": f"{half_up(per_egg, 1):g}",
                     "uk": band["size"], "shelled": fmt_g(shelled[e["shelled"]])})
    return rows


# ---------------------------------------------------------------- roasts
def roast_minutes(per450, extra, kg):
    """Q Guild formula, rounded UP to the next 5 minutes. Must match static/js/roast.js."""
    raw = per450 * (kg * 1000 / 450) + extra
    return int(math.ceil(raw / 5 - 1e-9) * 5)


def fmt_duration(m):
    h, mm = divmod(m, 60)
    if not h:
        return f"{mm} min"
    hs = "1 hour" if h == 1 else f"{h} hours"
    return hs if not mm else f"{hs} {mm} min"


def fmt_kg(kg):
    return f"{kg:g}kg"


def oven_text(meat):
    parts = []
    for st in meat["oven"]["stages"]:
        t = f"{st['c']}°C ({st['f']}°F, gas mark {st['gas']})"
        if st.get("note"):
            t += " " + st["note"]
        parts.append(t)
    return ", then ".join(parts)


def roast_rows(meat):
    rows = []
    for kg in meat["weights"]:
        row = {"kg": fmt_kg(kg), "lb": f"{half_up(kg * 2.20462, 1):g}"}
        if "doneness" in meat:
            row["times"] = [fmt_duration(roast_minutes(d["per450"], d["extra"], kg)) for d in meat["doneness"]]
        else:
            row["times"] = [fmt_duration(roast_minutes(meat["per450"], meat["extra"], kg))]
        rows.append(row)
    return rows


def roast_meats():
    out = []
    for m in ROASTS["meats"]:
        m = dict(m)
        m["url"] = f"/roast-timer/{m['slug']}/"
        m["oven_text"] = oven_text(m)
        m["rows"] = roast_rows(m)
        if "doneness" in m:
            mid = m["doneness"][1]
            m["rule"] = "; ".join(f"{d['label'].lower()}: {d['per450']} min per 450g plus {d['extra']} min" for d in m["doneness"])
            m["per_kg_text"] = ", ".join(f"{d['label'].lower()} about {int(half_up(d['per450'] * 1000 / 450))} min per kg plus {d['extra']}" for d in m["doneness"])
        else:
            m["rule"] = f"{m['per450']} minutes per 450g, plus {m['extra']} minutes"
            m["per_kg_text"] = f"about {int(half_up(m['per450'] * 1000 / 450))} minutes per kg, plus {m['extra']}"
        out.append(m)
    return out


def roast_weight_pages(m):
    pages = []
    if not m.get("weight_pages"):
        return pages
    for kg in m["weights"]:
        mins = roast_minutes(m["per450"], m["extra"], kg)
        pages.append({"kg": kg, "label": fmt_kg(kg), "lb": f"{half_up(kg * 2.20462, 1):g}",
                      "time": fmt_duration(mins), "minutes": mins,
                      "url": f"{m['url']}{fmt_kg(kg)}/"})
    return pages


def days_text(hours):
    """Hours as days, rounded UP to the next half day: 60 -> 'about 2½ days'."""
    half_days = math.ceil(hours / 12 - 1e-9)
    whole, half = divmod(half_days, 2)
    txt = (str(whole) if whole else "") + ("½" if half else "")
    return f"about {txt} day" + ("" if half_days == 2 else "s")


def thaw_rows():
    t = XMAS["thaw"]
    return [{"kg": fmt_kg(kg), "lb": f"{half_up(kg * 2.20462, 1):g}",
             "hmin": int(kg * t["hours_per_kg_min"]), "hmax": int(kg * t["hours_per_kg_max"]),
             "days": days_text(kg * t["hours_per_kg_max"])} for kg in t["weights"]]


# ---------------------------------------------------------------- Thanksgiving (USDA FSIS, pounds and °F)
def fmt_hours(m):
    """Minutes as USDA writes them: 165 -> '2¾ hours'. FSIS times are all whole quarter hours."""
    q = int(round(m / 15))
    whole, frac = divmod(q, 4)
    txt = (str(whole) if whole else "") + ["", "¼", "½", "¾"][frac]
    return txt + (" hour" if q == 4 else " hours")


def fmt_hour_range(a, b):
    lo, hi = fmt_hours(a), fmt_hours(b)
    return f"{lo.rsplit(' ', 1)[0]} to {hi}"


def turkey_rows(kind):
    return [dict(r, label=f"{r['lo']} to {r['hi']} lb" + (" (breast)" if r.get("breast") else ""),
                 time=fmt_hour_range(r["min"], r["max"])) for r in TG[kind]]


def turkey_range(lb, kind):
    """USDA rows that include this weight. A weight on a boundary (12 lb) sits in two rows,
    so the range runs from the lower row's shortest time to the upper row's longest.
    Must match static/js/thanksgiving.js."""
    rows = [r for r in TG[kind] if r["lo"] <= lb <= r["hi"] and not r.get("breast")]
    rows = rows or [r for r in TG[kind] if r["lo"] <= lb <= r["hi"]]
    if not rows:
        return None
    return {"min": rows[0]["min"], "max": rows[-1]["max"], "rows": [dict(r, label=f"{r['lo']} to {r['hi']} lb",
            time=fmt_hour_range(r["min"], r["max"])) for r in rows]}


def thaw_days(lb):
    """Fridge: 24 hours per 4 to 5 lb, shown in half days rounded up. Cold water: 30 min per lb."""
    t = TG["thaw"]
    def half(x):
        h = math.ceil(x * 2 - 1e-9) / 2
        whole, half_ = divmod(int(h * 2), 2)
        return (str(whole) if whole else "") + ("½" if half_ else "")
    lo, hi = half(lb / t["fridge_lb_per_day_max"]), half(lb / t["fridge_lb_per_day_min"])
    days = f"{lo} to {hi} days" if lo != hi else f"{hi} days"
    return {"fridge": days, "water": fmt_duration(int(lb * t["water_min_per_lb"]))}


def turkey_weight_pages():
    out = []
    for lb in TG["weight_pages"]:
        u, s = turkey_range(lb, "unstuffed"), turkey_range(lb, "stuffed")
        out.append({"a": "an" if str(lb).startswith(("8", "11", "18")) else "a", "lb": lb, "kg": f"{half_up(lb / 2.20462, 1):g}", "url": f"/thanksgiving-turkey-cooking-times/{lb}-lb/",
                    "un": u, "st": s, "un_time": fmt_hour_range(u["min"], u["max"]),
                    "st_time": fmt_hour_range(s["min"], s["max"]), "thaw": thaw_days(lb)})
    return out


# ---------------------------------------------------------------- render
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True,
                  trim_blocks=True, lstrip_blocks=True)
env.globals.update(site=SITE, today=TODAY, measures=MEASURES, usda_meta=USDA)


def asset(path):
    """URL for a static file with a content hash, so browsers fetch new versions after every change."""
    import hashlib
    digest = hashlib.sha256((ROOT / "static" / path.lstrip("/")).read_bytes()).hexdigest()[:10]
    return f"{path}?v={digest}"


env.globals["asset"] = asset


def page_title(t):
    """Search engines show about 70 characters. Drop the site name rather than cut the title."""
    full = f"{t} | {SITE['name']}"
    return full if len(full) <= 70 else t


def trim_desc(d, limit=160):
    """Keep meta descriptions within 160 characters, ending on a full sentence where possible."""
    d = " ".join(d.split())
    if len(d) <= limit:
        return d
    cut = d[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "))
    if end >= 80:
        return cut[:end + 1]
    cut = d[:limit - 3]
    return cut[:cut.rfind(" ")].rstrip(",;:") + "..."


env.globals["page_title"] = page_title
env.filters["trim_desc"] = trim_desc


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

    meats = roast_meats()
    by_slug = {it["slug"]: it for it in items}
    turkey = next(m for m in meats if m["slug"] == "turkey")
    gm4 = next(r for r in OVEN["rows"] if r["gas"] == "4")
    t5 = roast_minutes(turkey["per450"], turkey["extra"], 5)
    env.globals.update(
        nav_groups=by_group, nav_meats=meats,
        popular=[
            {"label": "1 cup of plain flour", "value": f"{fmt_g(by_slug['plain-flour']['units']['cup']['g'])}g", "url": "/convert/plain-flour/1-cup-to-grams/"},
            {"label": "1 stick of butter", "value": f"{fmt_g(by_slug['butter']['units']['stick']['g'])}g", "url": "/convert/butter/1-stick-to-grams/"},
            {"label": "1 cup of sugar", "value": f"{fmt_g(by_slug['granulated-sugar']['units']['cup']['g'])}g", "url": "/convert/granulated-sugar/1-cup-to-grams/"},
            {"label": "Gas mark 4", "value": f"{gm4['c']}°C", "url": "/oven-temperatures/"},
            {"label": "5kg turkey", "value": f"{t5 // 60}h {t5 % 60}m", "url": "/roast-timer/turkey/5kg/"},
        ],
    )

    for it in items:
        qp = quantity_pages(it)
        rp = reverse_pages(it)
        related = [o for o in by_group[it["group"]] if o["slug"] != it["slug"]][:6]
        urls.append(write(it["url"], "ingredient.html", item=it, qpages=qp, rpages=rp, rrows=reverse_rows(it),
                          related=related, title=f"{it['name']}: cups to grams", page_kind="ingredient"))
        for p in rp:
            urls.append(write(p["url"], "reverse.html", item=it, p=p, others=[o for o in rp if o["g"] != p["g"]],
                              qpages=qp, title=f"{p['g']}g of {it['name'].lower()} in cups", page_kind="quantity"))
        for p in qp:
            others = [o for o in qp if o["slug"] != p["slug"]]
            urls.append(write(p["url"], "quantity.html", item=it, p=p, others=others,
                              title=f"{p['phrase'].capitalize()} of {it['name'].lower()} in grams",
                              page_kind="quantity"))

    urls.append(write("/", "home.html", groups=by_group, title="Kitchen conversions that get to the point", page_kind="home"))
    urls.append(write("/convert/", "converter.html", groups=by_group, title="Cups to grams converter", page_kind="tool"))
    urls.append(write("/oven-temperatures/", "oven.html", oven=OVEN, title="Oven temperature converter: °C, fan, °F and gas mark", page_kind="tool"))
    urls.append(write("/recipe-scaler/", "scaler.html", title="Recipe scaler", page_kind="tool"))
    roast_js = {"meats": [{k: m[k] for k in ("slug", "name", "label", "per450", "extra", "doneness", "oven", "rest", "core", "range", "cooked_through") if k in m}
                          for m in meats]}
    (DIST / "js" / "roasts.json").write_text(json.dumps(roast_js, separators=(",", ":"), ensure_ascii=False))
    urls.append(write("/roast-timer/", "roast.html", meats=meats, roasts=ROASTS,
                      title="Roast timer: turkey, chicken, beef, lamb, pork and gammon", page_kind="tool"))
    for m in meats:
        wp = roast_weight_pages(m)
        urls.append(write(m["url"], "roast_meat.html", m=m, wpages=wp, meats=meats, roasts=ROASTS,
                          title=f"How long to roast a {m['label'].lower()}", page_kind="roast"))
        for p in wp:
            urls.append(write(p["url"], "roast_weight.html", m=m, p=p, wpages=wp, roasts=ROASTS,
                              title=f"How long to cook a {p['label']} {m['name'].lower()}", page_kind="roast"))

    (DIST / "js" / "christmas.json").write_text(json.dumps(
        {"thaw": XMAS["thaw"], "potatoes": XMAS["potatoes"], "sides": XMAS["sides"]}, separators=(",", ":"), ensure_ascii=False))
    urls.append(write("/christmas-dinner-planner/", "christmas.html", meats=meats, xmas=XMAS,
                      title="Christmas dinner planner: your timetable for the day", page_kind="tool"))
    urls.append(write("/how-long-to-defrost-a-turkey/", "thaw.html", thaw=XMAS["thaw"], rows=thaw_rows(),
                      safety=XMAS["safety"], src=XMAS["sources"]["fss"],
                      title="How long to defrost a turkey", page_kind="tool"))

    tg_pages = turkey_weight_pages()
    (DIST / "js" / "thanksgiving.json").write_text(json.dumps(
        {k: TG[k] for k in ("unstuffed", "stuffed", "thaw", "rest_min", "safe_f", "oven_f")}, separators=(",", ":"), ensure_ascii=False))
    tg_ctx = dict(tg=TG, src=TG["source"], un_rows=turkey_rows("unstuffed"), st_rows=turkey_rows("stuffed"), tg_pages=tg_pages)
    urls.append(write("/thanksgiving-dinner-planner/", "thanksgiving.html", **tg_ctx,
                      title="Thanksgiving dinner planner: when the turkey goes in", page_kind="tool"))
    urls.append(write("/thanksgiving-turkey-cooking-times/", "turkey_us.html", **tg_ctx,
                      title="Turkey cooking times by pound at 325°F", page_kind="roast"))
    for p in tg_pages:
        urls.append(write(p["url"], "turkey_us_weight.html", **tg_ctx, p=p,
                          title=f"How long to cook {p['a']} {p['lb']} lb turkey", page_kind="roast"))
    urls.append(write("/how-long-to-thaw-a-turkey/", "thaw_us.html", **tg_ctx,
                      title="How long to thaw a turkey: fridge and cold water", page_kind="tool"))

    tpages = [tin_page(f, t) for f, t in tin_pairs()]
    urls.append(write("/cake-tin-converter/", "tin.html", tpages=tpages, equiv=tin_equivalents(),
                      rounds=TIN_ROUND, squares=TIN_SQUARE,
                      title="Cake tin converter: scale a recipe to a different tin", page_kind="tool"))
    for tp in tpages:
        same = [o for o in tpages if o["from"] == tp["from"] and o is not tp]
        urls.append(write(tp["url"], "tin_pair.html", p=tp, others=same,
                          title=f"{tp['from_label'].capitalize()} tin to {tp['to_label']} tin", page_kind="tool"))

    yp = yeast_pages()
    (DIST / "js" / "yeast.json").write_text(json.dumps(YE["yeast"], separators=(",", ":"), ensure_ascii=False))
    urls.append(write("/yeast-converter/", "yeast.html", ye=YE, ypages=yp,
                      title="Yeast converter: fresh, dried and instant yeast", page_kind="tool"))
    for p in yp:
        urls.append(write(p["url"], "yeast_pair.html", ye=YE, p=p, ypages=yp, title=p["title"], page_kind="tool"))
    urls.append(write("/egg-sizes/", "eggs.html", ye=YE, rows=egg_rows(),
                      title="Egg sizes: UK and US compared", page_kind="tool"))

    for name in ("about", "privacy", "contact", "sources", "disclaimer"):
        fields, body = md_page(name)
        urls.append(write(f"/{name}/", "page.html", body=body, title=fields["title"],
                          description=fields["description"], page_kind="page", items=items, roasts=ROASTS))
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
    # Page fingerprints, so the deploy can tell search engines only about pages that changed.
    import hashlib
    hashes = {}
    for u in urls:
        f = DIST / u.lstrip("/") / "index.html" if u.endswith("/") else DIST / u.lstrip("/")
        hashes[u] = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    (DIST / "page-hashes.json").write_text(json.dumps(hashes, separators=(",", ":"), sort_keys=True))
    if SITE.get("indexnow_key"):
        (DIST / f"{SITE['indexnow_key']}.txt").write_text(SITE["indexnow_key"])
    print(f"Built {len(urls)} pages into {DIST}")


if __name__ == "__main__":
    main()
    if "--serve" in sys.argv:
        import http.server, functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        print("Serving on http://localhost:8000")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()
