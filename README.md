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

### Phase 3: Async crawler - complete

The crawler now uses `asyncio` and `aiohttp` for concurrent I/O-bound fetching:

- shared `aiohttp.ClientSession` for connection reuse
- `asyncio.Semaphore(20)` to bound concurrent requests
- task-based batch processing with `asyncio.gather`
- async BFS traversal with a maximum crawl size
- async robots.txt loading and crawl-delay support
- HTTP status and HTML content-type checks
- request timeouts and network error handling
- a configurable User-Agent header

This baseline established the concurrent crawl loop and queue discipline for the
project.

### Phase 4: Resilience and retry policy - complete

The crawler now includes operational safeguards for real-world site behavior:

- explicit retryable vs non-retryable exception types
- `tenacity` backoff with jitter for transient 5xx and network failures
- `429 Too Many Requests` handling with optional `Retry-After` support
- graceful rate-limit pauses without crashing the crawl
- robots.txt enforcement before fetching a page
- skip logic for malformed links and disallowed paths
- bounded page caps and host-scoped BFS traversal

This phase focuses on making the crawler robust enough to keep crawling under
realistic failures instead of silently stopping at the first error.

### Phase 5: SQLite storage and resumable state - complete

The crawler now persists crawl state and extracted page content in SQLite:

- metadata records for URL, response status, fetch timestamp, and crawl status
- extracted page text stored separately from request metadata
- queued, processing, processed, and failed states
- recovery of queued or interrupted processing records on restart
- skipping of URLs that have already completed successfully or failed
- SQLite work dispatched through a thread pool so database I/O does not block
	the async crawl loop

This phase makes crawl progress durable across process restarts and provides a
local database for inspecting the collected content.

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

1. Performance benchmarking and tuning
2. Multi-process crawling and scope control
3. Distributed crawling and richer scheduling policies

Phases 1 through 5 are complete. The next milestone is performance
benchmarking and tuning.
