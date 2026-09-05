from __future__ import annotations

import logging
import random
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from urllib.parse import urlparse

import httpx

from scraperunner.config import ScrapeConfig
from scraperunner.fetcher import Fetcher
from scraperunner.models import PageResult
from scraperunner.parser import parse_page
from scraperunner.utils.pagination import paginated_urls
from scraperunner.utils.robots import RobotsCache
from scraperunner.utils.url import is_same_domain, normalize_url

log = logging.getLogger(__name__)


class Crawler:
    """Breadth-first crawler bounded by depth, page count and domain.

    Pages are fetched by a pool of workers; results are yielded as they
    complete, and newly found links join the queue at depth + 1.
    """

    def __init__(
        self,
        config: ScrapeConfig,
        fetcher: Fetcher,
        robots: RobotsCache | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self._config = config
        self._fetcher = fetcher
        self._robots = robots
        self._should_stop = should_stop or (lambda: False)
        self._throttle = HostThrottle(config.delay)

    def crawl(self) -> Iterator[PageResult]:
        """Yield one :class:`PageResult` per visited page."""
        config = self._config
        seeds = self._seed_urls()
        queue: deque[tuple[str, int]] = deque((url, 0) for url in seeds)
        visited: set[str] = set(seeds)
        pending: dict[Future, tuple[str, int]] = {}
        pages_done = 0

        pool = ThreadPoolExecutor(max_workers=config.concurrency, thread_name_prefix="fetch")
        try:
            while (queue or pending) and pages_done < config.max_pages and not self._should_stop():
                while queue and len(pending) < config.concurrency and pages_done + len(pending) < config.max_pages:
                    url, depth = queue.popleft()
                    if self._allowed(url):
                        pending[pool.submit(self._visit, url, depth)] = (url, depth)
                    else:
                        log.info("Blocked by robots.txt: %s", url)
                if not pending:
                    break

                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    _, depth = pending.pop(future)
                    result = future.result()
                    if result is None:  # skipped because a stop was requested
                        continue
                    pages_done += 1
                    if depth < config.depth:
                        for link in self._crawlable_links(result):
                            if link not in visited:
                                visited.add(link)
                                queue.append((link, depth + 1))
                    yield result
                    if self._should_stop():
                        return
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    def _seed_urls(self) -> list[str]:
        config = self._config
        raw = (
            paginated_urls(config.start_url, config.pages, config.page_pattern)
            if config.pages
            else [config.start_url]
        )
        seeds = []
        for url in raw:
            normalized = normalize_url(url, url)
            if normalized is None:
                raise ValueError(f"Invalid start URL: {url}")
            seeds.append(normalized)
        return seeds

    def _visit(self, url: str, depth: int) -> PageResult | None:
        self._throttle.wait(url)
        if self._should_stop():
            return None
        log.info("[depth %d] %s", depth, url)
        try:
            fetched = self._fetcher.fetch(url)
        except (httpx.HTTPError, RuntimeError, OSError) as exc:
            log.warning("Failed %s: %s", url, exc)
            return PageResult(url=url, status=0, depth=depth, error=str(exc))

        if not fetched.is_html:
            return PageResult(url=fetched.final_url, status=fetched.status, depth=depth)
        return parse_page(fetched, depth, with_text=self._config.extract_text, selectors=self._config.selectors)

    def _allowed(self, url: str) -> bool:
        return self._robots is None or self._robots.can_fetch(url)

    def _crawlable_links(self, page: PageResult) -> list[str]:
        if not self._config.same_domain:
            return page.links
        return [link for link in page.links if is_same_domain(link, self._config.start_url)]


class HostThrottle:
    """Keeps at least ``delay`` seconds (jittered by +-50%) between request starts to one host."""

    def __init__(self, delay: float) -> None:
        self._delay = delay
        self._next_start: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        if self._delay <= 0:
            return
        host = urlparse(url).netloc
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_start.get(host, now))
            self._next_start[host] = start + self._delay * random.uniform(0.5, 1.5)
        if start > now:
            time.sleep(start - now)
