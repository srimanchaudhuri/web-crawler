class RateLimitedError(Exception):
    """429 — retry, but honor Retry-After if present."""
    def __init__(self, retry_after: float | None):
        self.retry_after = retry_after

class RetryableError(Exception):
    """Transient — safe to retry with backoff+jitter (timeouts, 5xx, connection errors)."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

class NonRetryableError(Exception):
    """4xx like 400/404 — retrying is pointless, give up immediately."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code