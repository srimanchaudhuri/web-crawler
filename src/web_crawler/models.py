from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


class CrawlerConfig(BaseModel):
    """Configuration for the web crawler."""

    url: HttpUrl = Field(..., description="The seed URL to start crawling from")
    page_limit: int = Field(
        default=10000, gt=0, description="Maximum number of pages to crawl"
    )
    max_concurrent_requests: int = Field(
        default=20, gt=0, description="Maximum concurrent HTTP requests"
    )
    request_timeout: int = Field(
        default=5, gt=0, description="HTTP request timeout in seconds"
    )
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        ),
        description="User-Agent header for HTTP requests",
    )
    db_path: Path = Field(
        default=Path("data/crawler.db"),
        description="Path to the SQLite database file",
    )
    tags_to_strip: list[str] = Field(
        default=["script", "style", "noscript", "svg", "iframe", "template"],
        description="HTML tags to strip before extracting text content",
    )


class CrawlResult(BaseModel):
    """Result for a single crawled page."""

    url: str = Field(..., description="The URL that was crawled")
    status_code: int | None = Field(default=None, description="HTTP status code")
    content: str | None = Field(
        default=None, description="Extracted text content from the page"
    )
    fetched_at: str | None = Field(
        default=None, description="Timestamp when the page was fetched"
    )
    status: str = Field(
        ..., description="Crawl status: 'processed' or 'failed'"
    )
