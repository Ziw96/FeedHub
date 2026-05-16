"""Playwright-driven scraper for URA PMI Residential Transaction Search.

The page (https://eservice.ura.gov.sg/property-market-information/
pmiResidentialTransactionSearch) is a JSF app that:
  - actively 403s bare HTTP clients (no User-Agent / no JS execution)
  - holds form state in hidden ViewState fields, so each search is a postback
  - paginates via in-page links that mutate the same form

A headless browser is the pragmatic choice. The selectors below are best-guesses
based on URA's public PMI UI conventions. On the first local run, set
`--debug` to dump the rendered HTML + screenshots so you can verify and adjust
SELECTORS to match the live DOM. All selectors live in one place.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

from ura_scraper.parser import parse_results_table

log = logging.getLogger(__name__)

SEARCH_URL = (
    "https://eservice.ura.gov.sg/property-market-information/"
    "pmiResidentialTransactionSearch"
)

# Selectors — verify these on first local run with --debug.
# Update here only; no other module references the DOM directly.
SELECTORS = {
    # Filter inputs
    "property_type_select": "select[name*='propertyType'], select#propertyType",
    "district_select": "select[name*='postalDistrict'], select#postalDistrict",
    "period_select": "select[name*='period'], select#period",
    "search_button": "button:has-text('Search'), input[type='submit'][value*='Search']",
    # Results
    "results_table": "table.tbl, table.results, table:has(th:has-text('Project'))",
    "no_results": "text=/no record|no result/i",
    "next_page": "a:has-text('Next'), a[title='Next Page']",
    "active_page": "a.active, span.current, li.active",
}

# Property type filter — the URA dropdown groups apartments + condos under
# "Non-Landed". We pick that and then row-filter for Apartment/Condominium
# in parser.filter_apartments_and_condos_resale().
PROPERTY_TYPE_OPTION = "Non-Landed"

# Period selector — URA caps at 60 months. We pick the longest window.
PERIOD_OPTION_HINTS = ("60", "5 year", "Past 60")


@dataclass
class ScrapeConfig:
    districts: list[str]
    headless: bool = True
    debug_dir: Path | None = None
    slow_mo_ms: int = 0
    max_pages_per_district: int = 200
    nav_timeout_ms: int = 45_000
    inter_request_delay_s: float = 1.5


@contextmanager
def _browser(cfg: ScrapeConfig):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo_ms)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
            locale="en-SG",
        )
        try:
            yield context
        finally:
            context.close()
            browser.close()


def _select_by_text_contains(page: Page, selector: str, hints: tuple[str, ...]) -> bool:
    """Pick the first <option> whose visible text contains one of the hints."""
    options = page.locator(f"{selector} option").all()
    for opt in options:
        label = (opt.text_content() or "").strip()
        if any(h.lower() in label.lower() for h in hints):
            value = opt.get_attribute("value")
            page.select_option(selector, value=value)
            return True
    return False


def _dump(page: Page, debug_dir: Path, name: str) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(debug_dir / f"{name}.png"), full_page=True)
    (debug_dir / f"{name}.html").write_text(page.content(), encoding="utf-8")


def _scrape_district(page: Page, district: str, cfg: ScrapeConfig) -> Iterator[str]:
    """Run a search for one district and yield page HTML for each result page."""
    log.info("District %s: navigating", district)
    page.goto(SEARCH_URL, timeout=cfg.nav_timeout_ms, wait_until="domcontentloaded")

    if not _select_by_text_contains(
        page, SELECTORS["property_type_select"], (PROPERTY_TYPE_OPTION,)
    ):
        log.warning("District %s: could not select property type", district)

    try:
        page.select_option(SELECTORS["district_select"], label=district)
    except Exception:
        try:
            page.select_option(SELECTORS["district_select"], value=district)
        except Exception:
            if cfg.debug_dir:
                _dump(page, cfg.debug_dir, f"district-{district}-select-failed")
            raise

    _select_by_text_contains(page, SELECTORS["period_select"], PERIOD_OPTION_HINTS)

    page.click(SELECTORS["search_button"])
    try:
        page.wait_for_selector(
            f"{SELECTORS['results_table']}, {SELECTORS['no_results']}",
            timeout=cfg.nav_timeout_ms,
        )
    except PWTimeout:
        if cfg.debug_dir:
            _dump(page, cfg.debug_dir, f"district-{district}-no-results-timeout")
        return

    if page.locator(SELECTORS["no_results"]).count() > 0:
        log.info("District %s: no results", district)
        return

    pages_seen = 0
    while pages_seen < cfg.max_pages_per_district:
        pages_seen += 1
        html = page.content()
        if cfg.debug_dir:
            _dump(page, cfg.debug_dir, f"district-{district}-p{pages_seen}")
        yield html

        next_link = page.locator(SELECTORS["next_page"]).first
        if next_link.count() == 0 or not next_link.is_enabled():
            break
        try:
            next_link.click()
            page.wait_for_selector(SELECTORS["results_table"], timeout=cfg.nav_timeout_ms)
        except PWTimeout:
            log.warning("District %s: pagination timeout on page %d", district, pages_seen)
            break
        time.sleep(cfg.inter_request_delay_s)


def scrape(cfg: ScrapeConfig) -> Iterator:
    """Top-level entrypoint. Yields Transaction objects across all districts."""
    with _browser(cfg) as context:
        page = context.new_page()
        page.set_default_timeout(cfg.nav_timeout_ms)

        for district in cfg.districts:
            try:
                for html in _scrape_district(page, district, cfg):
                    for tx in parse_results_table(html):
                        tx.district = district
                        yield tx
            except Exception as exc:
                log.exception("District %s failed: %s", district, exc)
            time.sleep(cfg.inter_request_delay_s)
