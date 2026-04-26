from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict
from urllib import error, parse, request

from .config import load_json_config


X_API_BASE_URL = "https://api.x.com"
X_DEFAULT_MAX_ITEMS = 5
X_USER_AGENT = "FeedHub/0.1"


@dataclass
class XConfig:
    bearer_token: str
    api_base_url: str = X_API_BASE_URL
    default_max_items: int = X_DEFAULT_MAX_ITEMS


def load_x_config() -> XConfig:
    payload = load_json_config("x.json")
    required = ("bearer_token",)
    missing = [key for key in required if not payload.get(key)]
    if missing:
        missing_fields = ", ".join(missing)
        raise ValueError(f"Missing X config fields: {missing_fields}")

    default_max_items = int(payload.get("default_max_items", X_DEFAULT_MAX_ITEMS))
    if default_max_items < 1:
        raise ValueError("X config default_max_items must be greater than 0")

    api_base_url = str(payload.get("api_base_url", X_API_BASE_URL)).rstrip("/")
    return XConfig(
        bearer_token=str(payload["bearer_token"]),
        api_base_url=api_base_url or X_API_BASE_URL,
        default_max_items=default_max_items,
    )


def x_api_get_json(path: str, params: Dict[str, Any], config: XConfig) -> Dict[str, Any]:
    query = parse.urlencode(params, doseq=True)
    url = f"{config.api_base_url}{path}"
    if query:
        url = f"{url}?{query}"

    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {config.bearer_token}",
            "User-Agent": X_USER_AGENT,
        },
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        message = details or exc.reason
        raise RuntimeError(f"X API error ({exc.code}): {message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach X API: {exc}") from exc

    parsed = json.loads(body or "{}")
    if parsed.get("errors") and not parsed.get("data"):
        raise RuntimeError(f"X API returned errors: {json.dumps(parsed['errors'])}")
    return parsed
