from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .collectors import fetch_source_items
from .config import load_sources, project_root
from .models import Item


def data_dir() -> Path:
    return project_root() / "data"


def raw_items_path() -> Path:
    return data_dir() / "raw-items.jsonl"


def collect_all() -> List[Item]:
    items: List[Item] = []
    for source in load_sources():
        try:
            items.extend(fetch_source_items(source))
        except Exception as exc:
            print(f"[collect] failed for {source.id}: {exc}")
    deduped = dedupe_items(items)
    append_items(deduped)
    return deduped


def dedupe_items(items: Iterable[Item]) -> List[Item]:
    seen_urls = set()
    seen_hashes = set()
    seen_titles = set()
    output: List[Item] = []
    for item in items:
        norm_title = _normalize_title(item.title)
        if item.url in seen_urls:
            continue
        if item.content_hash and item.content_hash in seen_hashes:
            continue
        if norm_title in seen_titles:
            continue
        seen_urls.add(item.url)
        seen_hashes.add(item.content_hash)
        seen_titles.add(norm_title)
        output.append(item)
    return output


def append_items(items: Iterable[Item]) -> None:
    target = raw_items_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=True) + "\n")


def load_items() -> List[Item]:
    target = raw_items_path()
    if not target.exists():
        return []
    output: List[Item] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        output.append(Item(**json.loads(line)))
    return output


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())
