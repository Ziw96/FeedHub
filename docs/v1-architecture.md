# FeedHub v1 Architecture

## Goal

Build a daily job that reports AI breaking news from the past 24 hours, starting with a short list of official provider sources.

## Scope

Included in v1:

- OpenAI, Anthropic, Gemini, and DeepSeek official pages
- hourly collection
- daily digest generation
- exact and near-exact deduplication
- simple ranking based on recency and source priority

Deferred:

- blogger opinion ranking
- semantic clustering with embeddings
- email or Slack delivery
- Postgres-backed state

## Pipeline

### 1. Source registry

Store sources in `config/sources.json` with:

- `id`
- `name`
- `type`
- `url`
- `base_url`
- `priority`
- `official`
- `enabled`
- `latest_link_pattern` for HTML index pages
- `handle` and `max_items` for X sources

### 2. Collection

Run every hour:

- RSS sources: parse items directly
- HTML sources: fetch page, extract title, keep snapshot text
- X sources: resolve the account by handle, fetch recent posts, skip replies and reposts by default

Each collected record should be normalized into:

- `source_id`
- `source_name`
- `title`
- `url`
- `published_at`
- `collected_at`
- `summary`
- `content_hash`
- `official`
- `priority`

For sources that expose a news index, optionally follow the first matching article link before extracting readable content. This avoids pinning the collector to a dated article URL.

X credentials live in `config/x.json`. Followed accounts still live in `config/sources.json`, so adding a new account only requires a new enabled source entry.

### 3. Deduplication

Use a layered strategy:

- exact URL match
- content hash match
- normalized title match

This is enough for the first pass while the source list is small.

### 4. Ranking

Score candidates using:

- source priority
- official-source bonus
- recency bonus

In v1, this keeps the scoring explainable and easy to tune.

### 5. Digest generation

Run once daily:

- load items from the last 24 hours
- dedupe again at digest time
- sort by score descending
- emit top 10 items into a markdown digest

## Storage

Local files for v1:

- `data/raw-items.jsonl`
- `data/digests/YYYY-MM-DD.md`

This keeps bootstrapping friction low. Once signal quality is acceptable, move to Postgres.

## Scheduler recommendation

Preferred first deployment:

- `collect`: hourly cron
- `digest`: daily cron
- `push-telegram`: daily cron shortly after digest generation

Examples:

```cron
0 * * * * /path/to/FeedHub/scripts/run_collect.sh >> /path/to/FeedHub/logs/collect.log 2>&1
5 8 * * * /path/to/FeedHub/scripts/run_digest.sh >> /path/to/FeedHub/logs/digest.log 2>&1
10 8 * * * /path/to/FeedHub/scripts/run_push_digest.sh >> /path/to/FeedHub/logs/telegram.log 2>&1
```

## Suggested v2

- replace file storage with Postgres
- add article-body extraction
- add LLM summaries with citations
- add semantic clustering
- add richer X filtering and account-management workflows
