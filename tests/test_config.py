from src.feedhub.config import load_sources
from src.feedhub.x import load_x_config


def test_load_sources_keeps_existing_types_and_reads_x_fields(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.json").write_text(
        """
        [
          {
            "id": "openai-blog",
            "name": "OpenAI Blog",
            "type": "rss",
            "url": "https://openai.com/news/rss.xml",
            "base_url": "https://openai.com",
            "priority": 10,
            "official": true
          },
          {
            "id": "openai-x",
            "name": "OpenAI on X",
            "type": "x",
            "url": "https://x.com/OpenAI",
            "base_url": "https://x.com",
            "priority": 6,
            "official": false,
            "handle": "OpenAI",
            "max_items": 5
          }
        ]
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.feedhub.config.project_root", lambda: tmp_path)

    sources = load_sources()

    assert [source.type for source in sources] == ["rss", "x"]
    assert sources[0].latest_link_pattern == ""
    assert sources[1].handle == "OpenAI"
    assert sources[1].max_items == 5


def test_load_x_config_requires_bearer_token(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "x.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("src.feedhub.config.project_root", lambda: tmp_path)

    try:
        load_x_config()
    except ValueError as exc:
        assert "Missing X config fields: bearer_token" in str(exc)
    else:
        raise AssertionError("Expected load_x_config() to fail without bearer_token")
