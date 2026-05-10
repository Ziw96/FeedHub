from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import Source


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_sources(include_disabled: bool = False) -> List[Source]:
    config_path = project_root() / "config" / "sources.json"
    payload = json.loads(config_path.read_text())
    return [
        Source(**entry)
        for entry in payload
        if include_disabled or entry.get("enabled", True)
    ]


def load_json_config(name: str) -> Dict[str, Any]:
    config_path = project_root() / "config" / name
    return json.loads(config_path.read_text())
