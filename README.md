# FeedHub

FeedHub is a small-scope AI breaking news collector. The v1 goal is:

- collect updates from a short list of official AI provider pages
- normalize them into one common record shape
- deduplicate obvious repeats
- generate a daily digest covering the past 24 hours

This first version intentionally stays narrow:

- source types: `rss`, `html`, and `x`
- sources: official provider blogs and news pages
- storage: local JSON lines files
- delivery: stdout / file output

HTML sources can optionally follow a "latest article" link pattern from a general newsroom page before extracting readable content.

## Project layout

- `config/sources.json`: tracked sources
- `docs/v1-architecture.md`: implementation plan
- `src/feedhub/collectors.py`: source fetchers
- `src/feedhub/pipeline.py`: normalize, dedupe, and storage
- `src/feedhub/digest.py`: digest ranking and rendering
- `src/feedhub/main.py`: CLI entrypoint
- `src/feedhub/x.py`: X API config and client helpers

## Quick start

```bash
python3 -m src.feedhub.main collect
python3 -m src.feedhub.main digest
```

Collected data is written to `data/raw-items.jsonl` and digests to `data/digests/`.

For scheduled runs, use the shell wrappers:

```bash
./scripts/run_collect.sh
./scripts/run_digest.sh
./scripts/run_push_digest.sh
```

They automatically run from the repo root and prefer `.venv/bin/python` when it exists.
All wrappers delegate to the generic runner, so ad hoc commands can also use:

```bash
./scripts/run_feedhub.sh collect
./scripts/run_feedhub.sh monitor-openai-releases
```

## X ingestion

Store X API settings in `config/x.json`:

```json
{
  "bearer_token": "replace-me",
  "default_max_items": 5,
  "api_base_url": "https://api.x.com"
}
```

Add followed X accounts to `config/sources.json` as regular sources:

```json
{
  "id": "openai-x",
  "name": "OpenAI on X",
  "type": "x",
  "url": "https://x.com/OpenAI",
  "base_url": "https://x.com",
  "priority": 6,
  "official": false,
  "enabled": true,
  "handle": "OpenAI",
  "max_items": 5
}
```

The existing `collect` command automatically picks up enabled X sources. If an enabled X source is missing credentials or has invalid credentials, collection prints a clear failure for that source and continues with the rest.

## Telegram delivery

Store Telegram bot settings in `config/telegram.json`:

```json
{
  "bot_token": "123456:replace-me",
  "chat_id": "replace-me",
  "parse_mode": "",
  "disable_web_page_preview": true
}
```

Then send the latest digest with:

```bash
./scripts/run_push_digest.sh
```

For a full daily schedule, run digest generation first and push a few minutes later.

## OpenAI model release monitor

To watch OpenAI model releases, ChatGPT model picker/default changes, and model availability updates, run:

```bash
./scripts/run_openai_release_monitor.sh
```

The first run records a baseline and does not push historical items. Later runs send matching new changes to the Telegram channel configured in `config/telegram.json`.
The monitored pages live in `config/sources.json`; release-specific keywords live in `config/openai_release_keywords.json`.

Example cron:

```cron
0 9 * * * /path/to/FeedHub/scripts/run_openai_release_monitor.sh >> /path/to/FeedHub/logs/openai-release-monitor.log 2>&1
```

## Next steps

- move storage to Postgres
- add richer HTML extraction
- add semantic clustering
- add scheduled hourly collection and daily delivery
- add richer X filtering controls
