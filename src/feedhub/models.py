from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Source:
    id: str
    name: str
    type: str
    url: str
    base_url: str
    priority: int
    official: bool
    enabled: bool = True
    latest_link_pattern: str = ""
    handle: str = ""
    max_items: int = 0


@dataclass
class Item:
    source_id: str
    source_name: str
    title: str
    url: str
    collected_at: str
    published_at: Optional[str] = None
    summary: str = ""
    content_hash: str = ""
    official: bool = False
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
