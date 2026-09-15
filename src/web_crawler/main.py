import asyncio
import aiohttp
from async_lru import alru_cache

from urllib.parse import urljoin, urlsplit
from selectolax.lexbor import LexborHTMLParser
from collections import deque
from urllib.robotparser import RobotFileParser

from utils.normalize_url import normalize_url

site_url_1 = 'https://www.scrapethissite.com/pages'
MAX_LINKS = 500
MAX_CONCURRENT_REQUESTS = 20
REQUEST_TIMEOUT = 5

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')

semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


async def get_link_tree(
    session: aiohttp.ClientSession,
    url: str,
    robot_parser: RobotFileParser,
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

    try:
        async with semaphore:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                headers={'User-Agent': USER_AGENT},
            ) as res:
                final_url = str(res.url)
                if robot_parser.can_fetch('*', final_url) is False:
                    print(f'Redirected to disallowed URL {final_url} — skipping')
                    return None, None
                if urlsplit(final_url).path == '/robots.txt':
                    return None, None

                if res.status != 200 or not res.headers.get('Content-Type', '').startswith('text/html'):
                    print(f'Error fetching {url}: Status code {res.status}, '
                          f'Content-Type {res.headers.get("Content-Type")}')
                    return None, None
                text = await res.text()
                return LexborHTMLParser(text), res
    except aiohttp.ClientError as e:
        print(f'Network error fetching {url}: {e}')
        return None, None
    except asyncio.TimeoutError:
        print(f'Timed out fetching {url}')
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
) -> list[str]:
    if not robot_parser.can_fetch('*', seed_url):
        print(f"Access to {seed_url} is disallowed by robots.txt")
        return []

    queue: deque[asyncio.Task] = deque(
        [asyncio.create_task(get_link_tree(session, normalize_url(seed_url), robot_parser))]
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
                    queue.append(asyncio.create_task(get_link_tree(session, link, robot_parser)))

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
    host = urlsplit(site_url_1).hostname
    rp = await get_robots(host)
    async with aiohttp.ClientSession() as session:
        results = await link_bfs(session, site_url_1, host, rp)

    print(f"Found {len(results)} links on {site_url_1}:")
    for link in results:
        print(link)


if __name__ == '__main__':
    asyncio.run(main())