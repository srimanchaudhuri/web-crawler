import requests
from urllib.parse import urljoin
from selectolax.lexbor import LexborHTMLParser
site_url = 'https://www.scrapethissite.com/pages'

def get_link_tree(url) -> tuple[LexborHTMLParser, str]:
    r = requests.get(url, timeout=10)

    return LexborHTMLParser(r.text), r.url

def main():
    tree, base_url = get_link_tree(site_url)
    for link in tree.css('a'):
        href = link.attributes.get('href')

        if href:
            print(urljoin(base_url, href))

if __name__ == '__main__':
    main()