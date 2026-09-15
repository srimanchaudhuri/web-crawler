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

### Phase 2: Sequential BFS crawler - complete

The project has moved beyond single-page fetching and now includes the core
structure of a queue-based crawler:

- breadth-first traversal with `collections.deque`
- URL normalization and canonicalization before deduplication
- `visited` and `queued` sets to avoid reprocessing the same page
- same-host filtering for basic crawl scope control
- link extraction from discovered pages
- robots.txt integration hook for crawl policy checks

This milestone established the crawler frontier, URL policy, and deduplication
behavior used by the async implementation.

### Phase 3: Async crawler - mostly complete

The crawler now uses `asyncio` and `aiohttp` for concurrent I/O-bound fetching:

- shared `aiohttp.ClientSession` for connection reuse
- `asyncio.Semaphore(20)` to bound concurrent requests
- task-based batch processing with `asyncio.gather`
- async BFS traversal with a maximum crawl size
- async robots.txt loading and crawl-delay support
- HTTP status and HTML content-type checks
- request timeouts and network error handling
- a configurable User-Agent header

The core Phase 3 implementation is working. Timing comparisons between the
sequential and async crawlers, plus retry/backoff behavior, are intentionally
left for the later performance and resilience checkpoints.

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

1. Politeness, retries, and resilience
2. SQLite storage and resumable state
3. Performance benchmarking and tuning
4. Multi-process crawling and scope control
