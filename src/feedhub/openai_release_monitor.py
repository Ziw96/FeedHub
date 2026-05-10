from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .collectors import fetch_source_items
from .config import load_sources, project_root
from .models import Item, Source
from .telegram import send_text


MONITORED_SOURCE_IDS = {
    "chatgpt-release-notes",
    "openai-blog",
    "model-release-notes",
}

DEFAULT_KEYWORDS = [
    "gpt-",
    "gpt ",
    "o1",
    "o3",
    "o4",
    "codex",
    "sora",
    "model picker",
    "switch model",
    "model switch",
    "default model",
    "new model",
    "available in chatgpt",
    "rollout",
    "rolling out",
    "deprecated",
    "deprecation",
    "retire",
]


@dataclass
class MonitorCheck:
    updates: List[Item]
    next_state: Dict[str, Any]


def check_and_push() -> List[Item]:
    check = prepare_update_check()
    if check.updates:
        send_text(format_updates(check.updates))
    save_state(check.next_state)
    return check.updates


def prepare_update_check(now: datetime | None = None) -> MonitorCheck:
    now = now or datetime.now(timezone.utc)
    keywords = load_monitor_keywords()
    state = load_state()
    seen_hashes = set(state.get("seen_hashes", []))
    initialized = bool(state.get("initialized"))

    fetched = fetch_updates()
    matching = [item for item in fetched if is_relevant(item, keywords)]
    new_updates = [item for item in matching if item.content_hash not in seen_hashes]

    next_state = {
        **state,
        "initialized": True,
        "last_checked_at": now.replace(microsecond=0).isoformat(),
        "seen_hashes": sorted(seen_hashes | {item.content_hash for item in matching}),
    }
    return MonitorCheck(updates=new_updates if initialized else [], next_state=next_state)


def load_monitor_keywords() -> List[str]:
    config_path = project_root() / "config" / "openai_release_keywords.json"
    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        return payload.get("keywords") or DEFAULT_KEYWORDS
    return DEFAULT_KEYWORDS


def state_path() -> Path:
    return project_root() / "data" / "openai-release-monitor-state.json"


def load_state() -> Dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: Dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch_updates() -> List[Item]:
    items: List[Item] = []
    for source in monitored_sources():
        items.extend(fetch_source_items(source))
    return items


def monitored_sources() -> List[Source]:
    return [
        source
        for source in load_sources(include_disabled=True)
        if source.id in MONITORED_SOURCE_IDS
    ]


def is_relevant(item: Item, keywords: Iterable[str]) -> bool:
    haystack = item.summary.lower()
    if item.source_id == "openai-blog":
        haystack = f"{item.title}\n{item.summary}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def format_updates(updates: List[Item]) -> str:
    lines = ["OpenAI model release monitor", ""]
    for update in updates:
        lines.extend(
            [
                f"{update.title}",
                f"Source: {update.source_name}",
                f"URL: {update.url}",
            ]
        )
        if update.published_at:
            lines.append(f"Published: {update.published_at}")
        if update.summary:
            lines.append(f"Summary: {truncate(update.summary, 700)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    shortened = value[:limit].rsplit(" ", 1)[0].strip()
    return f"{shortened}..."
