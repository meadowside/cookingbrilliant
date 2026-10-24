"""Check our committed USDA weights against the official FoodData Central SR Legacy CSV.

Usage: python scripts/verify_fdc.py PATH_TO_UNZIPPED_SR_LEGACY_CSV

data/usda_portions.json was extracted from the SR28 ASCII files. SR Legacy in
FoodData Central is the same data, republished with FDC IDs. This script maps
each NDB number to its FDC ID and confirms every gram weight we use appears in
FDC's food_portion.csv with the same measure name. Exit code 1 on any mismatch.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find(base, name):
    hits = list(Path(base).rglob(name))
    if not hits:
        sys.exit(f"{name} not found under {base}")
    return hits[0]


def main(base):
    ours = json.loads((ROOT / "data" / "usda_portions.json").read_text())["foods"]
    ndb_to_fdc = {}
    with open(find(base, "sr_legacy_food.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ndb_to_fdc[r["NDB_number"].zfill(5)] = r["fdc_id"]

    fdc_portions = {}
    with open(find(base, "food_portion.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            label = (r.get("modifier") or r.get("portion_description") or "").strip()
            fdc_portions.setdefault(r["fdc_id"], []).append(
                (float(r["amount"] or 0), label, float(r["gram_weight"]))
            )

    problems = 0
    for ndb, food in ours.items():
        fdc_id = ndb_to_fdc.get(ndb)
        if not fdc_id:
            print(f"MISSING  NDB {ndb} has no FDC ID")
            problems += 1
            continue
        theirs = fdc_portions.get(fdc_id, [])
        for p in food["portions"]:
            match = [t for t in theirs if t[1] == p["measure"] and abs(t[2] - p["grams"]) < 0.01]
            if not match:
                print(f"DIFF     NDB {ndb} (FDC {fdc_id}) {p['amount']:g} {p['measure']} = {p['grams']:g}g "
                      f"not in FDC. FDC has: {theirs}")
                problems += 1
    print(f"Checked {len(ours)} foods, {problems} problem(s).")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
