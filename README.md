# FeedHub — URA Property Scraper (prototype)

A CLI prototype that pulls **resale transactions for Apartments and Condominiums**
from URA Singapore. Two interchangeable data sources, picked at runtime:

- `--source api` — the official URA Data Service (recommended, default)
- `--source html` — a Playwright scrape of URA's public PMI search page

Designed to extend to Executive Condominium, Landed, New/Sub Sale, and
rentals later. Personal/research use only.

## Scope of v1

- Filters applied: `propertyType in ("Apartment", "Condominium")` AND
  `typeOfSale == "Resale"`
- Coverage: the rolling ~60-month / 5-year window URA exposes publicly
- Outputs: timestamped CSV + JSON under `./data/`
- Runtime: cron-friendly CLI (`python -m ura_scraper sync ...`)

## Install

```bash
pip install -r requirements.txt
# Only needed if you'll use --source html:
playwright install chromium
```

## Usage

### API mode (recommended)

```bash
# One-time: register for a free AccessKey at
#   https://eservice.ura.gov.sg/maps/api/reg.html
# Then export it (or pass via --access-key):
export URA_ACCESS_KEY="your-key-here"

# Full scrape — all districts, all of URA's rolling window.
python -m ura_scraper sync                       # source defaults to 'api'
python -m ura_scraper sync --source api

# Write to a custom directory
python -m ura_scraper sync --output ./data

# See everything URA returns (no apt/condo/resale filter)
python -m ura_scraper sync --no-filter
```

The first call each day mints a fresh token (URA tokens are daily, per
account); it gets cached at `~/.cache/ura_scraper/token.json` so repeated
runs the same day skip the round trip.

### HTML mode (fallback / no registration)

```bash
# All 28 districts, headless
python -m ura_scraper sync --source html

# A subset
python -m ura_scraper sync --source html --districts 9,10,11

# Watch the browser + dump HTML/screenshots for debugging selectors
python -m ura_scraper sync --source html --headed --debug --slow-mo 250 --districts 9
```

URA refreshes the underlying data every Tuesday and Friday (EOD). Cron
example for a Mac mini under `cron` (Wed + Sat morning):

```
0 9 * * 3,6  cd ~/Code/ura-scraper && /usr/bin/env python3 -m ura_scraper sync >> ~/Library/Logs/ura-scraper.log 2>&1
```

Or as a launchd plist if you prefer — same command, schedule via
`StartCalendarInterval`.

## Choosing a source

|                          | `api`                              | `html`                                |
| ------------------------ | ---------------------------------- | ------------------------------------- |
| One-time setup           | Email registration (~1 day)        | `playwright install chromium` (~300MB) |
| Runtime per full sync    | Seconds (4 HTTP requests)          | Several minutes (28 districts × pagination) |
| Robustness               | High (stable JSON contract)        | Brittle (DOM selectors, JSF state)    |
| 403/bot-block risk       | None                               | Real — URA actively filters bots      |
| Sanctioned for personal? | Yes (Singapore Open Data Licence)  | Ambiguous, treat as best-effort       |
| Refresh cadence          | Tue + Fri EOD                      | Same (same underlying data)           |

Strong recommendation: use `api`. The `html` path is kept as a fallback
and for cases where you can't register.

## Verifying HTML selectors on first run

If you're running `--source html`, the DOM selectors in
`ura_scraper/scraper.py` (`SELECTORS` dict, `PROPERTY_TYPE_OPTION`,
`PERIOD_OPTION_HINTS`) were written without live access to URA. On the
first local run:

1. `python -m ura_scraper sync --source html --headed --debug --districts 9`
2. Watch the browser and inspect `./debug/district-09-p1.html` if anything
   misbehaves.
3. Open the page in your browser, right-click each form control, and
   reconcile the `name`/`id` attributes with `SELECTORS`. All DOM strings
   live in one place by design.

## Architecture

```
ura_scraper/
├── cli.py         argparse entry: `python -m ura_scraper sync ...`
├── api_client.py  Official URA Data Service client (--source api)
├── scraper.py     Playwright HTML scraper (--source html)
├── parser.py      BeautifulSoup table parser + apt/condo/resale filter
├── writers.py     CSV + JSON output, timestamped filenames
├── models.py      Transaction dataclass (shared by both sources)
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
