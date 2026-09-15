class RetryableError(Exception):
    """Transient — safe to retry with backoff+jitter (timeouts, 5xx, connection errors)."""

class RateLimitedError(Exception):
    """429 — retry, but honor Retry-After if present."""
    def __init__(self, retry_after: float | None):
        self.retry_after = retry_after

class NonRetryableError(Exception):
    """4xx like 400/404 — retrying is pointless, give up immediately."""