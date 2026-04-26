from src.feedhub.collectors import _ReadableHTMLParser, _fetch_x_posts, _find_latest_link
from src.feedhub.models import Source
from src.feedhub.x import XConfig


def _parse(html: str) -> _ReadableHTMLParser:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    parser.close()
    return parser


def test_html_parser_drops_script_style_and_nav_noise():
    parser = _parse(
        """
        <html>
          <head>
            <title>Google DeepMind</title>
            <style>@keyframes slide { from { opacity: 0; } }</style>
          </head>
          <body>
            <header>Menu Pricing Docs</header>
            <main>
              <h1>Gemini 3 launches</h1>
              <p>The latest Gemini model improves agentic planning and coding quality.</p>
              <p>It is available today for developers.</p>
            </main>
            <script>window.__DATA__ = {"x": 1}</script>
          </body>
        </html>
        """
    )

    assert parser.best_title() == "Google DeepMind"
    summary = parser.summary()
    assert "Gemini 3 launches" in summary
    assert "agentic planning" in summary
    assert "@keyframes" not in summary
    assert "window.__DATA__" not in summary
    assert "Menu Pricing Docs" not in summary


def test_html_parser_prefers_meta_title_when_present():
    parser = _parse(
        """
        <html>
          <head>
            <meta property="og:title" content="DeepSeek-R1 Release" />
            <title>Fallback Title</title>
          </head>
          <body>
            <article>
              <p>DeepSeek-R1 reaches stronger reasoning performance on math and code tasks.</p>
            </article>
          </body>
        </html>
        """
    )

    assert parser.best_title() == "DeepSeek-R1 Release"
    assert "reasoning performance" in parser.summary()


def test_find_latest_link_picks_first_matching_news_href():
    html = """
    <html>
      <body>
        <a href="/news/news260424">DeepSeek-V4 Preview Release 2026/04/24</a>
        <a href="/news/news251201">DeepSeek-V3.2 Release 2025/12/01</a>
      </body>
    </html>
    """

    assert (
        _find_latest_link(html, "https://api-docs.deepseek.com/news", "/news/news")
        == "https://api-docs.deepseek.com/news/news260424"
    )


def test_fetch_x_posts_maps_payload_and_skips_replies_and_reposts(monkeypatch):
    source = Source(
        id="openai-x",
        name="OpenAI on X",
        type="x",
        url="https://x.com/OpenAI",
        base_url="https://x.com",
        priority=6,
        official=False,
        handle="OpenAI",
        max_items=5,
    )

    monkeypatch.setattr(
        "src.feedhub.collectors.load_x_config",
        lambda: XConfig(bearer_token="token", default_max_items=5),
    )

    def fake_x_api_get_json(path, params, config):
        assert config.bearer_token == "token"
        if path == "/2/users/by/username/OpenAI":
            return {"data": {"id": "42", "username": "OpenAI"}}
        if path == "/2/users/42/tweets":
            assert params["exclude"] == ["replies", "retweets"]
            return {
                "data": [
                    {
                        "id": "100",
                        "text": "OpenAI shipped a new safety and evals update for developers today.",
                        "created_at": "2026-04-26T08:15:00Z",
                    },
                    {
                        "id": "101",
                        "text": "This is a repost",
                        "created_at": "2026-04-26T08:20:00Z",
                        "referenced_tweets": [{"type": "retweeted", "id": "99"}],
                    },
                    {
                        "id": "102",
                        "text": "@someone Thanks for the feedback.",
                        "created_at": "2026-04-26T08:25:00Z",
                        "in_reply_to_user_id": "7",
                    },
                    {
                        "id": "103",
                        "text": "Short fallback",
                        "note_tweet": {
                            "text": "Longer update with release notes and rollout details for API users."
                        },
                        "created_at": "2026-04-26T08:30:00Z",
                    },
                ]
            }
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr("src.feedhub.collectors.x_api_get_json", fake_x_api_get_json)

    items = _fetch_x_posts(source)

    assert len(items) == 2
    assert items[0].url == "https://x.com/OpenAI/status/100"
    assert items[0].published_at == "2026-04-26T08:15:00+00:00"
    assert items[0].summary.startswith("OpenAI shipped a new safety")
    assert items[1].title.startswith("Longer update with release notes")
    assert items[1].url == "https://x.com/OpenAI/status/103"
