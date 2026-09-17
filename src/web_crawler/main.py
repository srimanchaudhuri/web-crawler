import asyncio
import datetime
from enum import Enum
from pathlib import Path
import sqlite3
import threading
import time
import aiohttp
from async_lru import alru_cache
from concurrent.futures import ThreadPoolExecutor

from urllib.parse import urljoin, urlsplit
from selectolax.lexbor import LexborHTMLParser
from collections import deque
from urllib.robotparser import RobotFileParser

from dbup.init_db import init_db
from utils.normalize_url import normalize_url
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from web_crawler.exception import NonRetryableError, RateLimitedError, RetryableError

site_url_1 = 'https://www.scrapethissite.com/pages'
tags_to_strip = ['script', 'style', 'noscript', 'svg', 'iframe', 'template']
MAX_LINKS = 10000
MAX_CONCURRENT_REQUESTS = 20
REQUEST_TIMEOUT = 5
DB_PATH = Path("data/crawler.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

init_db()

_local = threading.local()

class Status(Enum):
    processing = "processing"
    queued = "queued"
    processed = "processed"
    failed = "failed"

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')

semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def _get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "connection"):
        _local.connection = sqlite3.connect(DB_PATH)
        _local.connection.execute("PRAGMA foreign_keys = ON")
    return _local.connection

def _write_metadata_sync(url: str, status_code: int | None, timestamp: str, status: Status) -> int:
    conn = _get_connection()
    c = conn.cursor()
    with conn:
        c.execute("""
            INSERT INTO metadata (url, status_code, fetched_timestamp, status) VALUES (:url, :status_code, :fetched_timestamp, :status)
            ON CONFLICT(url)
            DO UPDATE SET 
                fetched_timestamp = excluded.fetched_timestamp,
                status = excluded.status,
                status_code = excluded.status_code
            RETURNING id;
        """,  {"url": url, "status_code": status_code, "fetched_timestamp": timestamp, "status": status.value})

        result = c.fetchone()
        row_id = result[0] if result else None

    return row_id

async def write_metadata(loop: asyncio.AbstractEventLoop, executor: ThreadPoolExecutor, url: str, status_code: int | None, timestamp: str, status: str) -> int:
    return await loop.run_in_executor(executor, _write_metadata_sync, url, status_code, timestamp, status)

def _write_data_sync(metadata_id: str, content: str):
    conn = _get_connection()
    c = conn.cursor()
    with conn:
        c.execute("""
            INSERT INTO data (metadata_id, content) VALUES (:metadata_id, :content)
            ON CONFLICT(metadata_id)
            DO UPDATE SET 
            content = excluded.content
        """,  {"metadata_id": metadata_id, "content": content})

async def write_data(loop: asyncio.AbstractEventLoop, executor: ThreadPoolExecutor, metadata_id: str, content: str):
    await loop.run_in_executor(executor, _write_data_sync, metadata_id, content)


async def _fetch(session: aiohttp.ClientSession, url: str, robot_parser: RobotFileParser) -> tuple[LexborHTMLParser, aiohttp.ClientResponse] | tuple[None, None]:
    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        headers={'User-Agent': USER_AGENT},
    ) as res:
        final_url = str(res.url)
        if robot_parser.can_fetch('*', final_url) is False:
            return None, None
        if urlsplit(final_url).path == '/robots.txt':
            return None, None

        if res.status == 429:
            retry_after = res.headers.get('Retry-After')
            raise RateLimitedError(float(retry_after) if retry_after else None)

        if 500 <= res.status < 600:
            raise RetryableError(f'{res.status} from {url}', res.status)

        if res.status != 200 or not res.headers.get('Content-Type', '').startswith('text/html'):
            raise NonRetryableError(f'{res.status} from {url}', res.status)

        text = await res.text()
        return LexborHTMLParser(text), res

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((RetryableError, aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True
)
async def fetch_with_retry(session: aiohttp.ClientSession, url: str, robot_parser: RobotFileParser) -> tuple[LexborHTMLParser, aiohttp.ClientResponse]:
        async with semaphore:
            return await _fetch(session, url, robot_parser)

async def get_link_tree(
    session: aiohttp.ClientSession,
    url: str,
    robot_parser: RobotFileParser,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop
) -> tuple[LexborHTMLParser, aiohttp.ClientResponse] | tuple[None, None]:
    if urlsplit(url).path == '/robots.txt':
        return None, None

    if robot_parser.can_fetch('*', url) is False:
        print(f"Access to {url} is disallowed by robots.txt")
        return None, None

    delay = robot_parser.crawl_delay('*')
    if delay is not None:
        await asyncio.sleep(delay)

    url = normalize_url(url)

    max_retries = 0
    while True and max_retries < 3:
        try:
            await write_metadata(loop, executor, url, None, str(datetime.datetime.now()), Status.processing)
            html, res = await fetch_with_retry(session, url, robot_parser)

            # NEW: guard against _fetch's clean (None, None) return
            # (robots-disallowed redirect target, or a redirect landing on /robots.txt)
            if html is None or res is None:
                return None, None

            id = await write_metadata(loop, executor, url, res.status, str(datetime.datetime.now()), Status.processed)

            html_copy = html.clone()
            html_copy.strip_tags(tags_to_strip)
            clean_text = html_copy.text(separator=" ", strip=True)
            content = " ".join(clean_text.split())
            await write_data(loop, executor, id, content)
            return html, res

        except RateLimitedError as e:
            retry_after = e.retry_after
            max_retries += 1
            if retry_after is not None:
                print(f"Rate limited on {url}, retrying after {retry_after} seconds")
                await asyncio.sleep(retry_after)
            else:
                print(f"Rate limited on {url}, retrying after 1 second")
                await asyncio.sleep(1)
        except NonRetryableError as e:
            print(f'Not retrying {url}: {e}')
            await write_metadata(loop, executor, url, e.status_code, str(datetime.datetime.now()), Status.failed)
            return None, None
        except (RetryableError, aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f'Gave up on {url} after 3 retries: {e}')
            await write_metadata(loop, executor, url, e.status_code, str(datetime.datetime.now()), Status.failed)
            return None, None

    await write_metadata(loop, executor, url, 429, str(datetime.datetime.now()), Status.failed)
    return None, None


def extract_links_from_page(html: LexborHTMLParser, base_url: str) -> list[str]:
    links = []
    for node in html.css('a'):
        href = node.attributes.get('href')
        if not href:
            continue
        try:
            links.append(normalize_url(urljoin(base_url, href)))
        except Exception as e:
            print(f'Skipping malformed link on {base_url}: {href!r} ({e})')
    return links

async def link_bfs(
    session: aiohttp.ClientSession,
    seed_url: str,
    host: str,
    robot_parser: RobotFileParser,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop
) -> list[str]:
    if not robot_parser.can_fetch('*', seed_url):
        print(f"Access to {seed_url} is disallowed by robots.txt")
        return []

    queue: deque[asyncio.Task] = deque(
        [asyncio.create_task(get_link_tree(session, normalize_url(seed_url), robot_parser, executor, loop))]
    )
    visited: set[str] = set()
    queued: set[str] = set()

    while queue and len(visited) < MAX_LINKS:
        batch = list(queue)
        queue.clear()
        results = await asyncio.gather(*batch)

        for html, res in results:
            if html is None or res is None:
                continue

            page_url = normalize_url(str(res.url))
            visited.add(page_url)

            for link in extract_links_from_page(html, str(res.url)):
                if (
                    link not in visited
                    and link not in queued
                    and urlsplit(link).hostname == host
                    and len(visited) + len(queued) < MAX_LINKS
                ):
                    queued.add(link)
                    queue.append(asyncio.create_task(get_link_tree(session, link, robot_parser, executor, loop)))
                    await write_metadata(loop, executor, link, None, str(datetime.datetime.now()), Status.queued)


    return list(visited)[:MAX_LINKS]


@alru_cache(maxsize=32)
async def get_robots(host: str) -> RobotFileParser:
    rp = RobotFileParser()
    robots_url = f'https://{host}/robots.txt'
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                robots_url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                headers={'User-Agent': USER_AGENT},
            ) as res:
                text = await res.text()
                rp.parse(text.splitlines())
        except aiohttp.ClientError as e:
            print(f'Could not fetch robots.txt for {host}: {e} — treating as fully allowed')
            rp.parse([])
    return rp


async def main():
    loop = asyncio.get_running_loop()
    db_executor = ThreadPoolExecutor(max_workers=1)

    host = urlsplit(site_url_1).hostname
    rp = await get_robots(host)
    async with aiohttp.ClientSession() as session:
        await link_bfs(session, site_url_1, host, rp, db_executor, loop)

    db_executor.shutdown(wait=True)


if __name__ == '__main__':
    asyncio.run(main())