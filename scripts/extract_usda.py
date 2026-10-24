"""Pull household-measure gram weights for our ingredients out of USDA SR Legacy.

SR Legacy is the final release of USDA's Standard Reference database (SR28), now
served through FoodData Central. Its data is CC0 / public domain.

Usage:
    python scripts/extract_usda.py PATH_TO_SR28_ASCII_DIR

PATH must contain FOOD_DES.txt and WEIGHT.txt from the SR28 ASCII release
(caret-delimited, tilde-quoted). Writes data/usda_portions.json, which the site
build reads. Nothing in that file is typed by hand.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_sr(path):
    with open(path, encoding="latin-1") as f:
        for line in f:
            yield [c.strip("~") for c in line.rstrip("\r\n").split("^")]


def main(sr_dir):
    sr_dir = Path(sr_dir)
    ingredients = json.loads((ROOT / "data" / "ingredients.json").read_text())
    wanted = {i["ndb"] for i in ingredients}

    foods = {r[0]: r[2] for r in read_sr(sr_dir / "FOOD_DES.txt") if r[0] in wanted}
    portions = {}
    for r in read_sr(sr_dir / "WEIGHT.txt"):
        if r[0] in wanted:
            portions.setdefault(r[0], []).append(
                {"amount": float(r[2]), "measure": r[3], "grams": float(r[4])}
            )

    missing = sorted(wanted - set(foods))
    if missing:
        sys.exit(f"NDB numbers not found in SR Legacy: {missing}")

    out = {
        "source": "USDA FoodData Central, SR Legacy (April 2018 release, equivalent to SR28)",
        "licence": "CC0 1.0 (public domain)",
        "url": "https://fdc.nal.usda.gov/",
        "foods": {
            ndb: {"description": foods[ndb], "portions": portions.get(ndb, [])}
            for ndb in sorted(wanted)
        },
    }
    dest = ROOT / "data" / "usda_portions.json"
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {dest} with {len(out['foods'])} foods")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
