import asyncio

import aiohttp
from selectolax.lexbor import LexborHTMLParser
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from web_crawler.exception import NonRetryableError, RateLimitedError, RetryableError


async def _fetch(
    session: aiohttp.ClientSession,
    url: str,
    robot_parser: RobotFileParser,
    timeout: int,
    user_agent: str,
) -> tuple[LexborHTMLParser, aiohttp.ClientResponse] | tuple[None, None]:
    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={"User-Agent": user_agent},
    ) as res:
        final_url = str(res.url)
        if robot_parser.can_fetch("*", final_url) is False:
            return None, None
        if urlsplit(final_url).path == "/robots.txt":
            return None, None

        if res.status == 429:
            retry_after = res.headers.get("Retry-After")
            raise RateLimitedError(float(retry_after) if retry_after else None)

        if 500 <= res.status < 600:
            raise RetryableError(f"{res.status} from {url}", res.status)

        if res.status != 200 or not res.headers.get("Content-Type", "").startswith(
            "text/html"
        ):
            raise NonRetryableError(f"{res.status} from {url}", res.status)

        text = await res.text()
        return LexborHTMLParser(text), res


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type(
        (RetryableError, aiohttp.ClientError, asyncio.TimeoutError)
    ),
    reraise=True,
)
async def fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    robot_parser: RobotFileParser,
    semaphore: asyncio.Semaphore,
    timeout: int,
    user_agent: str,
) -> tuple[LexborHTMLParser, aiohttp.ClientResponse] | tuple[None, None]:
    async with semaphore:
        return await _fetch(session, url, robot_parser, timeout, user_agent)
