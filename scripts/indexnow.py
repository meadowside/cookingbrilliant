"""Tell IndexNow search engines (Bing and others) about pages that changed in this deploy.

Usage: python scripts/indexnow.py OLD_HASHES.json NEW_HASHES.json

OLD is the page-hashes.json fetched from the live site before the upload (may be missing
or empty on the first run). NEW is dist/page-hashes.json. Only new or changed pages are
sent. Set INDEXNOW_ALL=true to send every page (for a manual re-run). Never fails the deploy: problems are printed and the script exits 0.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "site.json").read_text())
ENDPOINT = "https://api.indexnow.org/indexnow"


def say(msg):
    """Print, and on GitHub Actions also show it as a notice on the run summary."""
    print(msg)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::notice title=IndexNow::{msg}")


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def main(old_path, new_path):
    key = SITE.get("indexnow_key")
    if not key:
        print("No indexnow_key in site.json, skipping.")
        return
    old, new = load(old_path), load(new_path)
    if os.environ.get("INDEXNOW_ALL") == "true":
        old = {}
    changed = sorted(u for u, h in new.items() if old.get(u) != h)
    say(f"{len(changed)} of {len(new)} pages new or changed.")
    if not changed:
        return
    base = SITE["base_url"]
    host = base.split("://", 1)[1]
    for i in range(0, len(changed), 10000):
        body = json.dumps({
            "host": host,
            "key": key,
            "keyLocation": f"{base}/{key}.txt",
            "urlList": [base + u for u in changed[i:i + 10000]],
        }).encode()
        req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                say(f"HTTP {r.status} for {len(changed[i:i + 10000])} URLs")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300].replace("\n", " ")
            say(f"HTTP {e.code} {e.reason}: {detail}")
        except Exception as e:
            say(f"request failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
