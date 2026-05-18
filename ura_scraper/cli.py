import argparse
import logging
import os
import sys
from pathlib import Path

from ura_scraper.districts import parse_district_arg
from ura_scraper.parser import filter_apartments_and_condos_resale
from ura_scraper.writers import write_outputs


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ura_scraper",
        description="Scrape URA Singapore private residential resale transactions.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Run a full scrape.")
    sync.add_argument(
        "--source",
        choices=("api", "html"),
        default="api",
        help="Data source: 'api' (official URA Data Service, recommended) "
             "or 'html' (Playwright scrape of the public PMI page).",
    )
    sync.add_argument("--output", default="./data", help="Output directory (default: ./data)")
    sync.add_argument(
        "--access-key",
        default=None,
        help="URA API AccessKey. Falls back to $URA_ACCESS_KEY. (api source only)",
    )
    sync.add_argument(
        "--districts",
        default="all",
        help="'all' or comma-separated postal district codes, e.g. '9,10,11'. "
             "(html source only; api always returns all districts)",
    )
    sync.add_argument("--headed", action="store_true",
                      help="Show the browser. (html source only)")
    sync.add_argument("--debug", action="store_true",
                      help="Dump HTML + screenshots to ./debug/. (html source only)")
    sync.add_argument("--slow-mo", type=int, default=0,
                      help="Playwright slow_mo ms. (html source only)")
    sync.add_argument(
        "--no-filter",
        action="store_true",
        help="Skip the apartment+condo resale filter; write everything returned.",
    )
    sync.add_argument("-v", "--verbose", action="store_true")
    return p


def _run_api(args) -> list:
    from ura_scraper.api_client import fetch_all_transactions
    access_key = args.access_key or os.environ.get("URA_ACCESS_KEY")
    return list(fetch_all_transactions(access_key))


def _run_html(args) -> list:
    from ura_scraper.scraper import ScrapeConfig, scrape
    districts = parse_district_arg(args.districts)
    cfg = ScrapeConfig(
        districts=districts,
        headless=not args.headed,
        debug_dir=Path("./debug") if args.debug else None,
        slow_mo_ms=args.slow_mo,
    )
    return list(scrape(cfg))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command != "sync":
        return 2

    try:
        rows = _run_api(args) if args.source == "api" else _run_html(args)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not args.no_filter:
        rows = filter_apartments_and_condos_resale(rows)

    label = f"ura_resale_{args.source}"
    meta = write_outputs(rows, Path(args.output), label=label)
    print(
        f"Wrote {meta['rows']} rows ({args.source})\n"
        f"  csv:  {meta['csv']}\n"
        f"  json: {meta['json']}"
    )
    return 0 if meta["rows"] > 0 else 1
