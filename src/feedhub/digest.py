from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from .config import project_root
from .models import Item
from .pipeline import dedupe_items, load_items


def build_daily_digest(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)
    candidates = [item for item in load_items() if _in_window(item, window_start, now)]
    ranked = sorted(dedupe_items(candidates), key=_score_item, reverse=True)[:10]

    date_label = now.date().isoformat()
    lines = [
        f"# AI Breaking News Digest - {date_label}",
        "",
        f"Window: {window_start.isoformat()} to {now.isoformat()}",
        "",
    ]
    if not ranked:
        lines.append("No items were collected in the last 24 hours.")
        return "\n".join(lines) + "\n"

    for index, item in enumerate(ranked, start=1):
        lines.extend(
            [
                f"## {index}. {item.title}",
                f"- Source: {item.source_name}",
                f"- URL: {item.url}",
                f"- Published: {item.published_at or 'unknown'}",
                f"- Summary: {item.summary or 'No summary available.'}",
                "",
            ]
        )
    return "\n".join(lines)


def write_daily_digest(now: datetime | None = None) -> Path:
    now = now or datetime.now(timezone.utc)
    digest_text = build_daily_digest(now)
    target = project_root() / "data" / "digests" / f"{now.date().isoformat()}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(digest_text, encoding="utf-8")
    return target


def _in_window(item: Item, start: datetime, end: datetime) -> bool:
    stamp = item.published_at or item.collected_at
    try:
        observed = datetime.fromisoformat(stamp)
    except ValueError:
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return start <= observed <= end


def _score_item(item: Item) -> tuple:
    recency = item.published_at or item.collected_at or ""
    official_bonus = 1 if item.official else 0
    return (item.priority, official_bonus, recency)
