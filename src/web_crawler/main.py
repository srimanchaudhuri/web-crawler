from web_crawler.crawler import Crawler
from web_crawler.models import CrawlerConfig

site_url = "https://www.scrapethissite.com/pages"


def main():
    config = CrawlerConfig(url=site_url, page_limit=10000)
    crawler = Crawler(config)
    results = crawler.crawl_sync()

    print(f"\nCrawled {len(results)} pages")
    for result in results[:5]:
        print(f"  {result.url} [{result.status}]")


if __name__ == "__main__":
    main()