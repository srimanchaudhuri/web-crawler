# Web Crawler

A small web crawler built from scratch in Python as a learning project.

## Current Progress

### Phase 1: Single-threaded fetcher - complete

- Fetches HTML with `requests`
- Parses HTML with `selectolax`
- Extracts links from `<a>` elements
- Resolves relative links with `urllib.parse.urljoin`
- Follows redirects by using the final response URL as the base URL
- Applies a 10-second request timeout

The crawler currently fetches the configured starting page and prints each
resolved link. It does not yet crawl linked pages, deduplicate URLs, or handle
robots.txt; those are planned for later phases.

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
