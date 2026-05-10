from datetime import datetime, timezone

from src.feedhub.models import Item
from src.feedhub.openai_release_monitor import (
    check_and_push,
    format_updates,
    is_relevant,
    prepare_update_check,
)


def _item(title, summary="", source_id="model-release-notes"):
    return Item(
        source_id=source_id,
        source_name="Model release notes",
        title=title,
        url="https://help.openai.com/en/articles/9624314-model-release-notes",
        collected_at="2026-05-10T00:00:00+00:00",
        summary=summary,
        published_at="2026-05-10T00:00:00+00:00",
        content_hash=f"hash-{title}-{summary}",
    )


def test_is_relevant_matches_model_and_switch_terms():
    assert is_relevant(_item("Release notes", "GPT-5.2 is now available"), ["gpt-"])
    assert is_relevant(_item("Release notes", "ChatGPT default model switch"), ["default model"])
    assert not is_relevant(_item("Model release notes", "Billing admin update"), ["model"])


def test_check_for_updates_baselines_first_run(monkeypatch):
    state = {}
    updates = [_item("Release notes", "GPT-5.2 is now available")]

    monkeypatch.setattr("src.feedhub.openai_release_monitor.load_monitor_keywords", lambda: ["gpt-"])
    monkeypatch.setattr("src.feedhub.openai_release_monitor.load_state", lambda: state)
    monkeypatch.setattr("src.feedhub.openai_release_monitor.fetch_updates", lambda: updates)

    result = prepare_update_check(datetime(2026, 5, 10, tzinfo=timezone.utc))

    assert result.updates == []
    assert result.next_state["initialized"] is True
    assert updates[0].content_hash in result.next_state["seen_hashes"]


def test_check_for_updates_returns_new_relevant_items_after_baseline(monkeypatch):
    old = _item("Release notes", "GPT-5.1 is now available")
    new = _item("Release notes", "GPT-5.2 is now available")
    state = {"initialized": True, "seen_hashes": [old.content_hash]}

    monkeypatch.setattr("src.feedhub.openai_release_monitor.load_monitor_keywords", lambda: ["gpt-"])
    monkeypatch.setattr("src.feedhub.openai_release_monitor.load_state", lambda: state)
    monkeypatch.setattr(
        "src.feedhub.openai_release_monitor.fetch_updates",
        lambda: [old, new, _item("Billing admin update")],
    )

    result = prepare_update_check(datetime(2026, 5, 10, tzinfo=timezone.utc))

    assert result.updates == [new]
    assert old.content_hash in result.next_state["seen_hashes"]
    assert new.content_hash in result.next_state["seen_hashes"]


def test_format_updates_includes_source_link_and_summary():
    text = format_updates([_item("GPT-5.2 is now available", "A better model is rolling out.")])

    assert "OpenAI model release monitor" in text
    assert "GPT-5.2 is now available" in text
    assert "Source: Model release notes" in text
    assert "A better model is rolling out." in text


def test_prepare_update_check_does_not_save_state(monkeypatch):
    monkeypatch.setattr("src.feedhub.openai_release_monitor.load_monitor_keywords", lambda: ["gpt-"])
    monkeypatch.setattr("src.feedhub.openai_release_monitor.load_state", lambda: {"initialized": True})
    monkeypatch.setattr(
        "src.feedhub.openai_release_monitor.fetch_updates",
        lambda: [_item("Release notes", "GPT-5.2 is now available")],
    )

    called = False

    def fake_save_state(_state):
        nonlocal called
        called = True

    monkeypatch.setattr("src.feedhub.openai_release_monitor.save_state", fake_save_state)

    prepare_update_check(datetime(2026, 5, 10, tzinfo=timezone.utc))

    assert called is False


def test_check_and_push_does_not_save_state_when_send_fails(monkeypatch):
    item = _item("Release notes", "GPT-5.2 is now available")
    check = type("Check", (), {"updates": [item], "next_state": {"seen_hashes": [item.content_hash]}})()
    monkeypatch.setattr("src.feedhub.openai_release_monitor.prepare_update_check", lambda: check)

    def fail_send(_text):
        raise RuntimeError("Telegram unavailable")

    monkeypatch.setattr("src.feedhub.openai_release_monitor.send_text", fail_send)

    called = False

    def fake_save_state(_state):
        nonlocal called
        called = True

    monkeypatch.setattr("src.feedhub.openai_release_monitor.save_state", fake_save_state)

    try:
        check_and_push()
    except RuntimeError as exc:
        assert "Telegram unavailable" in str(exc)
    else:
        raise AssertionError("Expected Telegram failure")

    assert called is False
