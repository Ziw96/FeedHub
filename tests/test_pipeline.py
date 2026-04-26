from src.feedhub.models import Item, Source
from src.feedhub.pipeline import collect_all


def test_collect_all_continues_when_one_source_fails(monkeypatch):
    sources = [
        Source(
            id="openai-x",
            name="OpenAI on X",
            type="x",
            url="https://x.com/OpenAI",
            base_url="https://x.com",
            priority=6,
            official=False,
            handle="OpenAI",
        ),
        Source(
            id="openai-blog",
            name="OpenAI Blog",
            type="rss",
            url="https://openai.com/news/rss.xml",
            base_url="https://openai.com",
            priority=10,
            official=True,
        ),
    ]
    returned_items = [
        Item(
            source_id="openai-blog",
            source_name="OpenAI Blog",
            title="OpenAI launches new model",
            url="https://openai.com/index/model",
            collected_at="2026-04-26T09:00:00+00:00",
            published_at="2026-04-26T08:00:00+00:00",
            summary="A new model is available.",
            content_hash="abc123",
            official=True,
            priority=10,
        )
    ]

    monkeypatch.setattr("src.feedhub.pipeline.load_sources", lambda: sources)

    def fake_fetch_source_items(source):
        if source.type == "x":
            raise RuntimeError("Missing X config fields: bearer_token")
        return returned_items

    monkeypatch.setattr("src.feedhub.pipeline.fetch_source_items", fake_fetch_source_items)
    monkeypatch.setattr("src.feedhub.pipeline.append_items", lambda items: None)

    items = collect_all()

    assert items == returned_items
