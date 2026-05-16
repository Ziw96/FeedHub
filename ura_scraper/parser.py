"""Parse URA PMI transaction results HTML into Transaction objects.

The page is a JSF/Struts app rendering a standard HTML table. Column order
observed on the public search results (left to right):

    S/N | Project Name | Street Name | Type | Postal District |
    Market Segment | Tenure | Type of Sale | No. of Units |
    Price ($) | Nett Price ($) | Area (Sqft) | Type of Area |
    Floor Level | Unit Price ($psf) | Date of Sale

This module is defensive: it identifies columns by header text rather than
position, so minor column reorderings don't break the parser. If URA changes
header wording, update HEADER_ALIASES.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterator

from bs4 import BeautifulSoup

from ura_scraper.models import Transaction


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "project": ("project name", "project"),
    "street": ("street name", "street"),
    "property_type": ("type", "property type"),
    "district": ("postal district", "district"),
    "market_segment": ("market segment",),
    "tenure": ("tenure",),
    "type_of_sale": ("type of sale",),
    "no_of_units": ("no. of units", "no of units", "number of units"),
    "price": ("price ($)", "transacted price ($)", "price"),
    "area_sqft": ("area (sqft)", "area sqft"),
    "area_sqm": ("area (sqm)", "area sqm"),
    "type_of_area": ("type of area",),
    "floor_range": ("floor level", "floor range"),
    "unit_price_psf": ("unit price ($psf)", "unit price psf", "$psf"),
    "contract_date": ("date of sale", "sale date", "contract date"),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _to_int(s: str) -> int | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d-]", "", s)
    return int(cleaned) if cleaned else None


def _to_float(s: str) -> float | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", s)
    return float(cleaned) if cleaned else None


def _map_headers(header_cells: list[str]) -> dict[str, int]:
    """Map our canonical field names to column indexes in the table."""
    norm = [_normalize(c) for c in header_cells]
    mapping: dict[str, int] = {}
    for field_name, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                mapping[field_name] = norm.index(alias)
                break
    return mapping


def parse_results_table(html: str, scraped_at: str | None = None) -> list[Transaction]:
    """Extract Transaction rows from a results-page HTML fragment."""
    soup = BeautifulSoup(html, "lxml")

    table = soup.find("table", class_=re.compile("tbl|result|search", re.I))
    if table is None:
        tables = soup.find_all("table")
        table = max(tables, key=lambda t: len(t.find_all("tr")), default=None)
    if table is None:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    header_cells = [c.get_text() for c in rows[0].find_all(["th", "td"])]
    col = _map_headers(header_cells)
    if "project" not in col or "price" not in col:
        return []

    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    out: list[Transaction] = []

    for tr in rows[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < len(header_cells) - 1:
            continue

        def get(field: str) -> str:
            idx = col.get(field)
            return cells[idx] if idx is not None and idx < len(cells) else ""

        area_sqft = _to_float(get("area_sqft"))
        area_sqm = _to_float(get("area_sqm"))
        if area_sqft and not area_sqm:
            area_sqm = round(area_sqft * 0.09290304, 2)

        raw = {h: cells[i] if i < len(cells) else "" for i, h in enumerate(header_cells)}
        raw["_scraped_at"] = scraped_at

        out.append(
            Transaction(
                project=get("project"),
                street=get("street"),
                district=(get("district") or "").zfill(2),
                market_segment=get("market_segment") or None,
                property_type=get("property_type"),
                type_of_sale=get("type_of_sale"),
                contract_date=get("contract_date"),
                price_sgd=_to_int(get("price")),
                area_sqft=area_sqft,
                area_sqm=area_sqm,
                unit_price_psf=_to_int(get("unit_price_psf")),
                type_of_area=get("type_of_area") or None,
                tenure=get("tenure") or None,
                floor_range=get("floor_range") or None,
                no_of_units=_to_int(get("no_of_units")) or 1,
                raw=raw,
            )
        )
    return out


def filter_apartments_and_condos_resale(rows: Iterator[Transaction]) -> list[Transaction]:
    """Apply the v1 scope: resale of Apartment or Condominium only."""
    allowed_types = {"apartment", "condominium"}
    return [
        t for t in rows
        if (t.property_type or "").strip().lower() in allowed_types
        and (t.type_of_sale or "").strip().lower() == "resale"
    ]
