import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ura_scraper.models import Transaction


CSV_FIELDS = [
    "project", "street", "district", "market_segment",
    "property_type", "type_of_sale", "contract_date",
    "price_sgd", "area_sqft", "area_sqm", "unit_price_psf",
    "type_of_area", "tenure", "floor_range", "no_of_units",
]


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_outputs(rows: Iterable[Transaction], output_dir: Path, label: str = "ura_resale") -> dict:
    """Write rows to {output_dir}/{label}-{ts}.csv and .json. Returns metadata."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _timestamp_slug()

    rows_list = list(rows)
    csv_path = output_dir / f"{label}-{slug}.csv"
    json_path = output_dir / f"{label}-{slug}.json"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for tx in rows_list:
            writer.writerow({k: tx.to_dict().get(k, "") for k in CSV_FIELDS})

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "row_count": len(rows_list),
                "rows": [tx.to_dict() for tx in rows_list],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    return {"csv": str(csv_path), "json": str(json_path), "rows": len(rows_list)}
