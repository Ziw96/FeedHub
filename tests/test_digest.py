from datetime import datetime, timezone

from src.feedhub.models import Item
from src.feedhub.digest import build_daily_digest


def test_digest_header_when_no_items(monkeypatch):
    monkeypatch.setattr("src.feedhub.digest.load_items", lambda: [])
    text = build_daily_digest(datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc))
    assert "# AI Breaking News Digest - 2026-04-24" in text
    assert "No items were collected in the last 24 hours." in text


def test_digest_ranks_official_source_ahead_of_x_when_timestamps_match(monkeypatch):
    shared_time = "2026-04-24T10:00:00+00:00"
    monkeypatch.setattr(
        "src.feedhub.digest.load_items",
        lambda: [
            Item(
                source_id="openai-x",
                source_name="OpenAI on X",
                title="X update",
                url="https://x.com/OpenAI/status/1",
                collected_at=shared_time,
                published_at=shared_time,
                summary="Update from X",
                content_hash="x1",
                official=False,
                priority=6,
            ),
            Item(
                source_id="openai-blog",
                source_name="OpenAI Blog",
                title="Official update",
                url="https://openai.com/index/1",
                collected_at=shared_time,
                published_at=shared_time,
                summary="Update from blog",
                content_hash="o1",
                official=True,
                priority=10,
            ),
        ],
    )

    text = build_daily_digest(datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc))

    assert text.index("## 1. Official update") < text.index("## 2. X update")
