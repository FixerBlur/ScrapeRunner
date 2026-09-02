from __future__ import annotations

import logging
import time

import httpx

from scraperunner.fetcher.base import Fetcher
from scraperunner.models import FetchResult

log = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_BACKOFF_SECONDS = 1.0


class HttpFetcher(Fetcher):
    """Plain HTTP fetcher over a shared client. Fast, no JavaScript execution.

    Network errors and transient server statuses are retried with a growing
    pause. The shared client is thread-safe, so one fetcher serves all workers.
    """

    def __init__(self, client: httpx.Client, retries: int = 2) -> None:
        self._client = client
        self._retries = max(0, retries)

    def fetch(self, url: str) -> FetchResult:
        for attempt in range(self._retries + 1):
            try:
                response = self._client.get(url)
            except httpx.TransportError as exc:
                if attempt == self._retries:
                    raise
                self._pause(attempt, url, str(exc))
                continue
            if response.status_code in _RETRY_STATUSES and attempt < self._retries:
                self._pause(attempt, url, f"HTTP {response.status_code}")
                continue
            content_type = response.headers.get("content-type", "")
            is_html = "html" in content_type or not content_type
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status=response.status_code,
                html=response.text if is_html else "",
                content_type=content_type,
            )
        raise AssertionError("unreachable")

    def _pause(self, attempt: int, url: str, reason: str) -> None:
        wait = _BACKOFF_SECONDS * (attempt + 1)
        log.info("Retry %d/%d for %s in %.0fs (%s)", attempt + 1, self._retries, url, wait, reason)
        time.sleep(wait)
