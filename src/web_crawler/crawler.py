import asyncio
import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit

import aiohttp
from selectolax.lexbor import LexborHTMLParser
from urllib.robotparser import RobotFileParser

from web_crawler.exception import NonRetryableError, RateLimitedError, RetryableError
from web_crawler.fetcher import fetch_with_retry
from web_crawler.models import CrawlerConfig, CrawlResult
from web_crawler.storage import CrawlStorage, Status
from web_crawler.normalize_url import normalize_url


class Crawler:
    """Async BFS web crawler with SQLite persistence and retry logic."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.storage = CrawlStorage(config.db_path)
        self._host = urlsplit(str(config.url)).hostname

    async def crawl(self) -> list[CrawlResult]:
        """Run the full BFS crawl and return results for all pages."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            robot_parser = await self._get_robots(self._host)
            async with aiohttp.ClientSession() as session:
                await self._link_bfs(
                    session,
                    str(self.config.url),
                    self._host,
                    robot_parser,
                    executor,
                    semaphore,
                )

            raw_results = await self.storage.get_all_results(executor)
            return [CrawlResult(**row) for row in raw_results]
        finally:
            executor.shutdown(wait=True)

    def crawl_sync(self) -> list[CrawlResult]:
        """Synchronous convenience wrapper around crawl()."""
        return asyncio.run(self.crawl())

    async def _get_link_tree(
        self,
        session: aiohttp.ClientSession,
        url: str,
        robot_parser: RobotFileParser,
        executor: ThreadPoolExecutor,
        semaphore: asyncio.Semaphore,
    ) -> tuple[LexborHTMLParser, aiohttp.ClientResponse] | tuple[None, None]:
        if urlsplit(url).path == "/robots.txt":
            return None, None

        if robot_parser.can_fetch("*", url) is False:
            print(f"Access to {url} is disallowed by robots.txt")
            return None, None

        delay = robot_parser.crawl_delay("*")
        if delay is not None:
            await asyncio.sleep(delay)

        url = normalize_url(url)

        max_retries = 0
        while max_retries < 3:
            try:
                await self.storage.write_metadata(
                    executor,
                    url,
                    None,
                    str(datetime.datetime.now()),
                    Status.processing,
                )
                html, res = await fetch_with_retry(
                    session,
                    url,
                    robot_parser,
                    semaphore,
                    self.config.request_timeout,
                    self.config.user_agent,
                )

                if html is None or res is None:
                    return None, None

                row_id = await self.storage.write_metadata(
                    executor,
                    url,
                    res.status,
                    str(datetime.datetime.now()),
                    Status.processed,
                )

                html_copy = html.clone()
                html_copy.strip_tags(self.config.tags_to_strip)
                clean_text = html_copy.text(separator=" ", strip=True)
                content = " ".join(clean_text.split())
                await self.storage.write_data(executor, row_id, content)
                return html, res

            except RateLimitedError as e:
                retry_after = e.retry_after
                max_retries += 1
                if retry_after is not None:
                    print(
                        f"Rate limited on {url}, retrying after {retry_after} seconds"
                    )
                    await asyncio.sleep(retry_after)
                else:
                    print(f"Rate limited on {url}, retrying after 1 second")
                    await asyncio.sleep(1)
            except NonRetryableError as e:
                print(f"Not retrying {url}: {e}")
                await self.storage.write_metadata(
                    executor,
                    url,
                    e.status_code,
                    str(datetime.datetime.now()),
                    Status.failed,
                )
                return None, None
            except (RetryableError, aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Gave up on {url} after 3 retries: {e}")
                status_code = getattr(e, "status_code", None)
                await self.storage.write_metadata(
                    executor,
                    url,
                    status_code,
                    str(datetime.datetime.now()),
                    Status.failed,
                )
                return None, None

        await self.storage.write_metadata(
            executor, url, 429, str(datetime.datetime.now()), Status.failed
        )
        return None, None

    @staticmethod
    def _extract_links(html: LexborHTMLParser, base_url: str) -> list[str]:
        links = []
        for node in html.css("a"):
            href = node.attributes.get("href")
            if not href:
                continue
            try:
                links.append(normalize_url(urljoin(base_url, href)))
            except Exception as e:
                print(f"Skipping malformed link on {base_url}: {href!r} ({e})")
        return links

    async def _link_bfs(
        self,
        session: aiohttp.ClientSession,
        seed_url: str,
        host: str,
        robot_parser: RobotFileParser,
        executor: ThreadPoolExecutor,
        semaphore: asyncio.Semaphore,
    ) -> list[str]:
        if not robot_parser.can_fetch("*", seed_url):
            print(f"Access to {seed_url} is disallowed by robots.txt")
            return []

        queue: deque[asyncio.Task] = deque()
        visited: set[str] = set()
        queued: set[str] = set()

        url_completed = await self.storage.is_completed(executor, seed_url)
        if not url_completed:
            queue.append(
                asyncio.create_task(
                    self._get_link_tree(
                        session,
                        normalize_url(seed_url),
                        robot_parser,
                        executor,
                        semaphore,
                    )
                )
            )

        stalled_records = await self.storage.get_stalled_records(executor)
        finished_records = await self.storage.get_finished_records(executor)

        for record in finished_records:
            visited.add(record["url"])

        for record in stalled_records:
            task = asyncio.create_task(
                self._get_link_tree(
                    session,
                    normalize_url(record["url"]),
                    robot_parser,
                    executor,
                    semaphore,
                )
            )
            queue.append(task)
            queued.add(record["url"])

        page_limit = self.config.page_limit
        while queue and len(visited) < page_limit:
            batch = list(queue)
            queue.clear()
            results = await asyncio.gather(*batch)

            for html, res in results:
                if html is None or res is None:
                    continue

                page_url = normalize_url(str(res.url))
                visited.add(page_url)

                for link in self._extract_links(html, str(res.url)):
                    if (
                        link not in visited
                        and link not in queued
                        and urlsplit(link).hostname == host
                        and len(visited) + len(queued) < page_limit
                    ):
                        queued.add(link)
                        queue.append(
                            asyncio.create_task(
                                self._get_link_tree(
                                    session,
                                    link,
                                    robot_parser,
                                    executor,
                                    semaphore,
                                )
                            )
                        )
                        await self.storage.write_metadata(
                            executor,
                            link,
                            None,
                            str(datetime.datetime.now()),
                            Status.queued,
                        )

        return list(visited)[:page_limit]

    async def _get_robots(self, host: str) -> RobotFileParser:
        rp = RobotFileParser()
        robots_url = f"https://{host}/robots.txt"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    robots_url,
                    timeout=aiohttp.ClientTimeout(total=self.config.request_timeout),
                    headers={"User-Agent": self.config.user_agent},
                ) as res:
                    text = await res.text()
                    rp.parse(text.splitlines())
            except aiohttp.ClientError as e:
                print(
                    f"Could not fetch robots.txt for {host}: {e} — treating as fully allowed"
                )
                rp.parse([])
        return rp
