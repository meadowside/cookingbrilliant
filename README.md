# cookingbrilliant.com

Kitchen conversions that answer the question in the first line. Static site: a Python build script turns JSON data into HTML, and the three tools run as plain JavaScript in the browser.

## Layout

```
build.py                  builds everything into dist/  (python build.py --serve to preview)
site.json                 site name, contact email, AdSense client ID, GA4 ID, sponsor slot
data/
  ingredients.json        the ingredient list: names, USDA record (NDB) number, which USDA measures to use
  usda_portions.json      gram weights extracted from USDA. Generated, never edited by hand
  measures.json           cup and spoon sizes in ml, each with a source
  oven.json               oven table (source: Which?)
  thanksgiving.json       US turkey times, thawing and safety (source: USDA FSIS)
content/*.md              about, contact, privacy, sources pages
templates/                Jinja2 templates
static/                   CSS, JS, fonts, favicon, .htaccess (copied into dist/ as is)
scripts/
  extract_usda.py         SR28 ASCII files -> data/usda_portions.json
  verify_fdc.py           checks usda_portions.json against the official FDC download
.github/workflows/
  deploy.yml              build and FTPS upload to Namecheap on every push to main
  verify-usda.yml         monthly re-check of the USDA numbers
```

## The data rule

Every number on the site traces to a source. Weights come from USDA FoodData Central SR Legacy (CC0). The build only does arithmetic on sourced numbers (half a cup is half the cup weight, a metric cup is the US cup scaled to 250ml) and the page says when it has. If a figure has no source, it doesn't go on the site.

## Adding an ingredient

1. Find the food in SR Legacy and note its NDB number and the exact measure names USDA uses (e.g. `cup, chopped`).
2. Add an entry to `data/ingredients.json`. `cup`, `tbsp`, `tsp` and `stick` take USDA measure names. `alt` lists extra measures to show.
3. Re-run the extraction: `python scripts/extract_usda.py PATH_TO_SR28_ASCII`. The SR28 ASCII files are mirrored at github.com/alyssaq/usda-sqlite (`data/` folder) and are identical to FDC's SR Legacy data.
4. `python build.py --serve` and check the page.

Ingredients USDA doesn't cover go in `data/other_sources.json`, quoting the source row exactly, and the ingredient entry uses `"src"` instead of `"ndb"`. Caster sugar (King Arthur Baking), double cream (FAO density database) and golden syrup (FSANZ specific gravity table) are done this way. Specific gravity is treated as g/ml.

## Deploying

Pushes to `main` build and upload `dist/` over FTPS. Add these repository secrets (Settings > Secrets and variables > Actions):

- `FTP_SERVER`: the hosting server name (`premium75.web-hosting.com`), not ftp.yourdomain, or the FTPS certificate check fails
- `FTP_USERNAME`, `FTP_PASSWORD`: a cPanel FTP account whose home directory is the cookingbrilliant.com document root

## Search engine notifications (IndexNow)

Each build writes `page-hashes.json` (a fingerprint of every page) and the IndexNow key file named after `indexnow_key` in `site.json`. After uploading, the deploy compares the new fingerprints with the ones that were live and sends only new or changed URLs to api.indexnow.org, which shares them with Bing and the other IndexNow engines. Google doesn't use IndexNow, so the sitemap still matters there.

## Turning on ads

1. Get AdSense approval for cookingbrilliant.com.
2. `adsense_client` in `site.json` holds the publisher ID. It adds the AdSense script and `ads.txt` to every build. The in-page ad slots stay hidden until `ad_units` is set to `true`, so there are no empty gaps while Google reviews the site.
3. In AdSense, Privacy & messaging, publish a European regulations message (Google's own consent tool) for UK, EEA and Swiss visitors. The footer's "Privacy and cookie settings" link reopens it.

## Google Analytics

Set `ga_measurement_id` in `site.json` to the GA4 measurement ID (starts `G-`) and push. That adds the Google tag to every page and switches the privacy page to its analytics wording. Set it back to `null` to remove both.

Consent is handled by the same Google consent message that covers AdSense: it passes the visitor's choice to Analytics through Consent Mode, so UK, EEA and Swiss visitors who refuse get no Analytics cookies.
