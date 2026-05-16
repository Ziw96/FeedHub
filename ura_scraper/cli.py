import argparse
import logging
import sys
from pathlib import Path

from ura_scraper.districts import parse_district_arg
from ura_scraper.parser import filter_apartments_and_condos_resale
from ura_scraper.scraper import ScrapeConfig, scrape
from ura_scraper.writers import write_outputs


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ura_scraper",
        description="Scrape URA Singapore private residential resale transactions.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Run a full scrape across selected districts.")
    sync.add_argument("--output", default="./data", help="Output directory (default: ./data)")
    sync.add_argument(
        "--districts",
        default="all",
        help="'all' or comma-separated postal district codes, e.g. '9,10,11'",
    )
    sync.add_argument("--headed", action="store_true", help="Show the browser (default: headless)")
    sync.add_argument("--debug", action="store_true", help="Dump HTML + screenshots to ./debug/")
    sync.add_argument("--slow-mo", type=int, default=0, help="Playwright slow_mo ms (debugging)")
    sync.add_argument(
        "--no-filter",
        action="store_true",
        help="Skip the apartment+condo resale filter; write everything returned.",
    )
    sync.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command != "sync":
        return 2

    try:
        districts = parse_district_arg(args.districts)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    cfg = ScrapeConfig(
        districts=districts,
        headless=not args.headed,
        debug_dir=Path("./debug") if args.debug else None,
        slow_mo_ms=args.slow_mo,
    )

    rows = list(scrape(cfg))
    if not args.no_filter:
        rows = filter_apartments_and_condos_resale(rows)

    meta = write_outputs(rows, Path(args.output))
    print(
        f"Wrote {meta['rows']} rows\n  csv:  {meta['csv']}\n  json: {meta['json']}"
    )
    return 0 if meta["rows"] > 0 else 1
