from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List
from urllib import error, parse, request

from .config import load_json_config, project_root


TELEGRAM_TEXT_LIMIT = 4000


def send_latest_digest() -> Path:
    config = load_telegram_config()
    digest_path = latest_digest_path()
    digest_text = digest_path.read_text(encoding="utf-8")
    chunks = chunk_message(digest_text, TELEGRAM_TEXT_LIMIT)
    for chunk in chunks:
        _send_message(config, chunk)
    return digest_path


def load_telegram_config() -> Dict[str, str]:
    payload = load_json_config("telegram.json")
    required = ("bot_token", "chat_id")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        missing_fields = ", ".join(missing)
        raise ValueError(f"Missing Telegram config fields: {missing_fields}")
    return payload


def latest_digest_path() -> Path:
    digest_dir = project_root() / "data" / "digests"
    candidates = sorted(digest_dir.glob("*.md"))
    if not candidates:
        raise FileNotFoundError("No digest files found in data/digests")
    return candidates[-1]


def chunk_message(text: str, limit: int) -> List[str]:
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for line in text.splitlines():
        addition = len(line) + (1 if current else 0)
        if current and current_len + addition > limit:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
            continue
        current.append(line)
        current_len += addition

    if current:
        chunks.append("\n".join(current))

    return chunks


def _send_message(config: Dict[str, str], text: str) -> None:
    api_url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
    payload = {
        "chat_id": config["chat_id"],
        "text": text,
        "disable_web_page_preview": bool(config.get("disable_web_page_preview", True)),
    }
    parse_mode = config.get("parse_mode", "")
    if parse_mode:
        payload["parse_mode"] = parse_mode

    encoded = parse.urlencode(payload).encode("utf-8")
    req = request.Request(api_url, data=encoded, method="POST")
    try:
        with request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach Telegram API: {exc}") from exc
    parsed = json.loads(body)
    if not parsed.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")
