# FeedHub — URA Property Scraper (prototype)

A CLI prototype that scrapes **resale transactions for Apartments and Condominiums**
from URA Singapore's public PMI search page. Designed to be extended to other
property types (Executive Condominium, Landed) and to rentals later.

## Scope of v1

- Source: <https://eservice.ura.gov.sg/property-market-information/pmiResidentialTransactionSearch>
- Filters applied: `propertyType in ("Apartment", "Condominium")` AND `typeOfSale == "Resale"`
- Coverage: the rolling 60-month window URA exposes publicly
- Outputs: timestamped CSV + JSON under `./data/`
- Runtime: cron-friendly CLI (`python -m ura_scraper sync ...`)

## Important caveat — why this uses a headless browser

URA's public search page actively rejects non-browser HTTP clients (returns
HTTP 403 to plain `curl`/`requests`) and stores form state in hidden JSF
ViewState fields, so each search is a postback. The robust path is a real
browser; this prototype uses **Playwright** headless Chromium.

URA also publishes a free official API (`PMI_Resi_Transaction`) that returns
the same data as clean JSON, refreshed every Tuesday and Friday. That route
is faster, less fragile, and explicitly sanctioned under the Singapore Open
Data Licence. If/when you want to switch, the `parser.py` and `writers.py`
modules drop in as-is — only `scraper.py` changes.

## Install

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
# Full scrape, all 28 districts, headless, write to ./data/
python -m ura_scraper sync

# Subset of districts
python -m ura_scraper sync --districts 9,10,11

# Watch it run + dump HTML/screenshots for debugging selectors
python -m ura_scraper sync --headed --debug --slow-mo 250 --districts 9

# Disable the apartment+condo+resale row filter (raw output)
python -m ura_scraper sync --no-filter --districts 9
```

Cron example (every Wednesday + Saturday morning, since URA refreshes Tue/Fri):

```
0 6 * * 3,6  cd /opt/feedhub && /usr/bin/python -m ura_scraper sync --output ./data >> ./logs/sync.log 2>&1
```

## Verifying selectors on first run

Because this sandbox can't reach `ura.gov.sg`, the DOM selectors in
`ura_scraper/scraper.py` (`SELECTORS` dict, `PROPERTY_TYPE_OPTION`,
`PERIOD_OPTION_HINTS`) are best-guesses based on URA's documented UI.
On your first local run:

1. `python -m ura_scraper sync --headed --debug --districts 9`
2. Watch the browser and inspect `./debug/district-09-p1.html` if anything
   misbehaves.
3. Open the page in your browser, right-click each form control, and reconcile
   the `name`/`id` attributes with the `SELECTORS` dict. All DOM strings live
   in one place by design.

## Architecture

```
ura_scraper/
├── cli.py         argparse entry: `python -m ura_scraper sync ...`
├── scraper.py     Playwright session: navigates, fills form, paginates
├── parser.py      BeautifulSoup table parser, defensive (header-driven)
├── writers.py     CSV + JSON output, timestamped filenames
├── models.py      Transaction dataclass
└── districts.py   Singapore postal districts 1-28
```

## Expanding scope

- **Add Executive Condominium**: extend `allowed_types` in
  `parser.filter_apartments_and_condos_resale` (rename it accordingly).
- **Include New Sale / Sub Sale**: drop the `type_of_sale` check in the same
  filter, or expose a `--sale-types` CLI flag.
- **Add Landed properties**: change `PROPERTY_TYPE_OPTION` in `scraper.py`,
  or run multiple passes selecting each option.
- **Add rentals**: target the sibling search page
  `pmiResidentialRentalSearch`. The parser is reusable with a different
  `HEADER_ALIASES` map.
- **Switch to the official URA API**: rewrite `scraper.py` only — `models`,
  `parser`'s output shape, `writers`, and `cli` stay. Register at
  <https://eservice.ura.gov.sg/maps/api/reg.html>; the relevant endpoint is
  `service=PMI_Resi_Transaction&batch=1..4`.

## Data freshness & legal notes

- URA refreshes caveats Tuesday + Friday EOD; records up to 60 months old
  may still amend/abort. Re-scrape the full window each run.
- Public PMI page Terms of Use should be reviewed before any commercial use.
  The official API is governed by the Singapore Open Data Licence and
  permits commercial use with attribution.
- Be a polite scraper: the default `inter_request_delay_s=1.5` paces requests.
  Don't lower it.
