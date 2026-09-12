# Web Crawler

A small web crawler built from scratch in Python as a learning project.

## Current Progress

### Phase 1: Single-threaded fetcher - complete

This milestone is complete and marks the end of the initial HTTP + HTML basics phase.

Covered:

- Fetching a page with `requests`
- Inspecting HTTP response metadata such as status code, headers, encoding, and elapsed time
- Parsing HTML with `selectolax`
- Extracting links from `<a>` tags
- Resolving relative URLs correctly with `urllib.parse.urljoin`
- Testing multiple sites and handling non-200 responses intentionally

The crawler currently fetches one or more configured starting pages and prints
resolved links. It does not yet crawl across discovered pages, deduplicate URLs,
or handle robots.txt; those belong to Phase 2.

## Setup

Install dependencies with [uv](https://docs.astral.sh/uv/):

```powershell
uv sync
```

## Run

```powershell
uv run python -m web_crawler.main
```

## Roadmap

1. Sequential crawling with URL deduplication and robots.txt support
2. Async crawling with `asyncio` and `aiohttp`
3. Politeness, retries, and resilience
4. SQLite storage and resumable state
5. Performance benchmarking and tuning
6. Multi-process crawling and scope control
