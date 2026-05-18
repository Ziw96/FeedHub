"""URA Data Service API client.

The official, sanctioned route. For personal/research use it's strictly
better than HTML scraping: 4 JSON requests instead of ~28 paginated form
postbacks, no DOM-selector breakage, refreshed Tue/Fri EOD by URA.

Auth flow:
  1. Register once at https://eservice.ura.gov.sg/maps/api/reg.html
     → you get a permanent AccessKey by email.
  2. Each day, exchange the AccessKey for a Token via /insertNewToken/v1.
  3. Every data request includes both `AccessKey` and `Token` headers.

This module caches the daily token at ~/.cache/ura_scraper/token.json so
repeated runs on the same day don't re-mint.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import time
from pathlib import Path
from typing import Iterator

import requests

from ura_scraper.models import Transaction

log = logging.getLogger(__name__)

TOKEN_URL = "https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1"
DATA_URL = "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1"
SERVICE = "PMI_Resi_Transaction"
BATCHES: tuple[int, ...] = (1, 2, 3, 4)

TOKEN_CACHE = Path(os.environ.get("URA_TOKEN_CACHE", "~/.cache/ura_scraper/token.json")).expanduser()

# URA returns typeOfSale as a single-digit code; map to human text.
TYPE_OF_SALE_MAP = {"1": "New Sale", "2": "Sub Sale", "3": "Resale"}


class URAAPIError(RuntimeError):
    pass


def _user_agent() -> str:
    return "ura_scraper/0.1 (personal research)"


def _to_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sqm_to_sqft(area_sqm: float | None) -> float | None:
    if area_sqm is None:
        return None
    return round(area_sqm / 0.09290304, 2)


def _decode_type_of_sale(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return TYPE_OF_SALE_MAP.get(s, s)


def _read_cached_token() -> str | None:
    if not TOKEN_CACHE.exists():
        return None
    try:
        cached = json.loads(TOKEN_CACHE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if cached.get("date") == dt.date.today().isoformat() and cached.get("token"):
        return cached["token"]
    return None


def _write_cached_token(token: str) -> None:
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE.write_text(json.dumps({"date": dt.date.today().isoformat(), "token": token}))


def get_token(access_key: str, *, force_refresh: bool = False) -> str:
    """Return today's URA Token, minting a new one if the cache is stale."""
    if not force_refresh:
        cached = _read_cached_token()
        if cached:
            log.debug("Using cached URA token")
            return cached

    log.info("Requesting new daily URA token")
    headers = {"AccessKey": access_key, "User-Agent": _user_agent()}
    r = requests.get(TOKEN_URL, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if payload.get("Status") != "Success" or not payload.get("Result"):
        raise URAAPIError(f"Token request failed: {payload}")
    token = payload["Result"]
    _write_cached_token(token)
    return token


def fetch_batch(access_key: str, token: str, batch: int) -> dict:
    """Fetch one batch of PMI_Resi_Transaction data."""
    headers = {
        "AccessKey": access_key,
        "Token": token,
        "User-Agent": _user_agent(),
    }
    params = {"service": SERVICE, "batch": str(batch)}
    log.info("Fetching %s batch %d", SERVICE, batch)
    r = requests.get(DATA_URL, headers=headers, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if payload.get("Status") != "Success":
        raise URAAPIError(f"Batch {batch} failed: {payload}")
    return payload


def _iter_transactions(payload: dict) -> Iterator[Transaction]:
    """URA's response nests transactions[] under each project entry."""
    for project_row in payload.get("Result", []):
        project = project_row.get("project") or ""
        street = project_row.get("street") or ""
        market_segment = project_row.get("marketSegment") or None
        for tx in project_row.get("transaction", []) or []:
            area_sqm = _to_float(tx.get("area"))
            yield Transaction(
                project=project,
                street=street,
                district=str(tx.get("district") or "").zfill(2),
                market_segment=market_segment,
                property_type=tx.get("propertyType") or "",
                type_of_sale=_decode_type_of_sale(tx.get("typeOfSale")),
                contract_date=tx.get("contractDate") or "",
                price_sgd=_to_int(tx.get("price")),
                area_sqm=area_sqm,
                area_sqft=_sqm_to_sqft(area_sqm),
                unit_price_psf=None,
                type_of_area=tx.get("typeOfArea"),
                tenure=tx.get("tenure"),
                floor_range=tx.get("floorRange"),
                no_of_units=_to_int(tx.get("noOfUnits")) or 1,
                raw={
                    **tx,
                    "_project": project,
                    "_street": street,
                    "_marketSegment": market_segment,
                },
            )


def fetch_all_transactions(
    access_key: str | None = None,
    *,
    batches: tuple[int, ...] = BATCHES,
    inter_request_delay_s: float = 0.5,
) -> Iterator[Transaction]:
    """Top-level entry: yield every transaction across all 4 batches."""
    access_key = access_key or os.environ.get("URA_ACCESS_KEY")
    if not access_key:
        raise URAAPIError(
            "No URA AccessKey. Set URA_ACCESS_KEY env var or pass --access-key. "
            "Register at https://eservice.ura.gov.sg/maps/api/reg.html"
        )
    token = get_token(access_key)

    for batch in batches:
        payload = fetch_batch(access_key, token, batch)
        yield from _iter_transactions(payload)
        if inter_request_delay_s > 0:
            time.sleep(inter_request_delay_s)
