import requests
from urllib.parse import urljoin
from selectolax.lexbor import LexborHTMLParser
site_url_1 = 'https://www.scrapethissite.com/pages'
site_url_2 = 'https://books.toscrape.com/'
site_url_3 = 'https://quotes.toscrape.com/'
site_url_4 = 'https://httpbin.org/status/403'
site_url_5 = 'https://httpbin.org/status/411'
site_url_6 = 'https://httpbin.org/status/404'
site_url_7 = 'https://httpbin.org/status/500'

def get_link_tree(url) -> tuple[LexborHTMLParser, requests.Response]:
    r = requests.get(url, timeout=10)
    return LexborHTMLParser(r.text), r

def print_metadata(response: requests.Response):
    print('\n\n--- Response Metadata ---\n\n')
    print(f'URL: {response.url}')
    print(f'Status Code: {response.status_code}')
    print(f'Content-Type: {response.headers.get("Content-Type")}')
    print(f'Content-Encoding: {response.headers.get("Content-Encoding")}')
    print(f'Encoding: {response.encoding}')
    print(f'Elapsed Time: {response.elapsed.total_seconds()} seconds')
    print(f'Response Headers: {response.headers}')

def main():
    for site_url in [site_url_1, site_url_2, site_url_3, site_url_4, site_url_5, site_url_6, site_url_7]:
        tree, response = get_link_tree(site_url)
        if response.status_code == 200:
            print(f'\n\n--- Crawling: {site_url} ---\n\n')
            print_metadata(response)
            print('\n\n--- Extracted Links ---\n\n')
            for link in tree.css('a'):
                href = link.attributes.get('href')
                if href:
                    print(urljoin(response.url, href))

        elif response.status_code == 500:
            print(f'\n\n--- Crawling: {site_url} ---\n\n')
            print_metadata(response)
            print('\n\n--- Error: Internal Server Error (500) ---\n\n')
            continue

        elif response.status_code == 404:
            print(f'\n\n--- Crawling: {site_url} ---\n\n')
            print_metadata(response)
            print('\n\n--- Error: Not Found (404) ---\n\n')
            continue

        elif response.status_code == 403:
            print(f'\n\n--- Crawling: {site_url} ---\n\n')
            print_metadata(response)
            print('\n\n--- Error: Forbidden (403) ---\n\n')
            continue

        elif response.status_code == 411:
            print(f'\n\n--- Crawling: {site_url} ---\n\n')
            print_metadata(response)
            print('\n\n--- Error: Length Required (411) ---\n\n')
            continue
        

if __name__ == '__main__':
    main()