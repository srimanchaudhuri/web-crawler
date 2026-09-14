from functools import lru_cache
import time

import requests
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from selectolax.lexbor import LexborHTMLParser
from collections import deque
from urllib.robotparser import RobotFileParser

example_url = 'https://www.Example.com:443/path/../folder?b=2&a=1&c=&x=7#section-2'
site_url_1 = 'https://www.scrapethissite.com/pages'
site_url_2 = 'https://books.toscrape.com'
site_url_3 = 'https://quotes.toscrape.com'
site_url_4 = 'https://httpbin.org/status/403'
site_url_5 = 'https://httpbin.org/status/411'
site_url_6 = 'https://httpbin.org/status/404'
site_url_7 = 'https://httpbin.org/status/500'
DEFAULT_PORTS = {'http': 80, 'https': 443}
MAX_LINKS = 500

def get_link_tree(url: str, crawl_delay: float | None) -> tuple[LexborHTMLParser, requests.Response]:
    try:
        if crawl_delay is not None:
            time.sleep(crawl_delay)
        url = normalize_url(url)
        r = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'})
        if r.status_code != 200 or not r.headers.get('Content-Type', '').startswith('text/html'):
            print(f'Error fetching {url}: Status code {r.status_code}, Content-Type {r.headers.get("Content-Type")}')
            return LexborHTMLParser(''), r
        return LexborHTMLParser(r.text), r
    except requests.exceptions.RequestException as e:
        print(f'Error fetching {url}: {e}')
        return LexborHTMLParser(''), None

def normalize_path(path: str) -> str:
    segments = path.split('/')
    normalized_segments = []
    for segment in segments:
        if segment == '..':
            if normalized_segments:
                normalized_segments.pop()
        elif segment == '.' or segment == '':
            continue
        else:
            normalized_segments.append(segment)

    return '/' + '/'.join(normalized_segments)

def normalize_query(query: str) -> str:
    query_params = parse_qs(query, keep_blank_values=True)
    sorted_params = sorted((key, value) for key, values in query_params.items() for value in values)
    return urlencode(sorted_params)

def normalize_url(url: str) -> str:
    url_parts = urlsplit(url)
    scheme = url_parts.scheme.lower()
    host = url_parts.hostname.lower() if url_parts.hostname else ''
    port = url_parts.port
    if port is not None and port == DEFAULT_PORTS.get(scheme):
        port = None    
    path = normalize_path(url_parts.path)
    query = normalize_query(url_parts.query)
    normalized_url = scheme + '://' + host
    if port:
        normalized_url += ':' + str(port)
    normalized_url += path
    if query:
        normalized_url += '?' + query
    return normalized_url

def print_metadata(response: requests.Response):
    print('\n\n--- Response Metadata ---\n\n')
    print(f'URL: {response.url}')
    print(f'Status Code: {response.status_code}')
    print(f'Content-Type: {response.headers.get("Content-Type")}')
    print(f'Content-Encoding: {response.headers.get("Content-Encoding")}')
    print(f'Encoding: {response.encoding}')
    print(f'Elapsed Time: {response.elapsed.total_seconds()} seconds')
    print(f'Response Headers: {response.headers}')

def link_bfs(url: str, host: str, robot_parser: RobotFileParser) -> list[str]:
    if not robot_parser.can_fetch('*', url):
        print(f"Access to {url} is disallowed by robots.txt")
        return []
    queue = deque([normalize_url(url)])
    visited = set()
    queued = set()
    extracted_links = []

    while queue and len(extracted_links) < MAX_LINKS:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        links, r = get_link_tree(current_url, robot_parser.crawl_delay('*'))
        if r is None or r.status_code != 200 or not r.headers.get('Content-Type', '').startswith('text/html'):
            continue
        extracted_links.append(current_url)
        for link in links.css('a'):
            href = link.attributes.get('href')
            if href:
                absolute_url = urljoin(current_url, href)
                absolute_url = normalize_url(absolute_url)
                if absolute_url not in visited and absolute_url not in queued and urlsplit(absolute_url).hostname == host and robot_parser.can_fetch('*', absolute_url) and urlsplit(absolute_url).path != '/robots.txt':
                    queue.append(absolute_url)
                    queued.add(absolute_url)

    return extracted_links

@lru_cache(maxsize=32)
def get_robots(url: str) -> RobotFileParser:
    rp = RobotFileParser()
    res = requests.get(urljoin(url, '/robots.txt'), headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'})
    rp.parse(res.text.splitlines())
    return rp

def main():
    try:
        rp = get_robots(site_url_1)
        extracted_links = link_bfs(site_url_1, urlsplit(site_url_1).hostname, rp)
        print(f'Extracted {len(extracted_links)} links from {site_url_1}:')
        for link in extracted_links:
            print(link)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()