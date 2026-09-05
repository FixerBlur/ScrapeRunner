import threading
import time

from scraperunner.config import FetchMode, ScrapeConfig
from scraperunner.crawler import Crawler, HostThrottle
from scraperunner.fetcher.base import Fetcher
from scraperunner.models import FetchResult


class SlowSite(Fetcher):
    """Every page links to five children; each fetch takes a moment and records its worker thread."""

    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.threads: set[str] = set()
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def fetch(self, url: str) -> FetchResult:
        with self._lock:
            self.threads.add(threading.current_thread().name)
            self.calls.append(url)
        time.sleep(self.delay)
        html = "".join(f'<a href="{url.rstrip("/")}/{n}">{n}</a>' for n in range(5))
        return FetchResult(url=url, final_url=url, status=200, html=html, content_type="text/html")


def crawl(**overrides):
    config = ScrapeConfig(start_url="https://s.com/", delay=0, respect_robots=False, mode=FetchMode.HTTP, **overrides)
    site = SlowSite()
    pages = list(Crawler(config, site).crawl())
    return pages, site


def test_workers_run_in_parallel_and_respect_max_pages():
    started = time.monotonic()
    pages, site = crawl(depth=2, max_pages=20, concurrency=5)
    elapsed = time.monotonic() - started

    assert len(pages) == 20
    assert len(site.calls) == 20                      # nothing fetched beyond the cap
    assert len(site.threads) > 1                      # more than one worker was used
    assert elapsed < 20 * 0.05                        # faster than sequential


def test_breadth_first_order_and_depth_limit():
    pages, _ = crawl(depth=1, max_pages=100, concurrency=3)
    assert [page.depth for page in pages] == [0] + [1] * 5
    assert len({page.url for page in pages}) == 6


def test_single_worker_is_sequential():
    pages, site = crawl(depth=1, max_pages=6, concurrency=1)
    assert len(site.threads) == 1
    assert len(pages) == 6


def test_stop_request_ends_the_crawl_before_the_next_fetch():
    config = ScrapeConfig(start_url="https://s.com/", depth=3, max_pages=100, delay=0, respect_robots=False, mode=FetchMode.HTTP, concurrency=4)
    site = SlowSite()
    seen = []
    crawler = Crawler(config, site, should_stop=lambda: len(seen) >= 2)
    for page in crawler.crawl():
        seen.append(page)
    assert len(seen) == 2
    assert len(site.calls) <= 2 + config.concurrency  # in-flight fetches at most, nothing after


def test_host_throttle_spaces_requests_per_host():
    throttle = HostThrottle(delay=0.1)
    started = time.monotonic()
    throttle.wait("https://a.com/1")
    throttle.wait("https://b.com/1")      # other host: no wait
    assert time.monotonic() - started < 0.05
    throttle.wait("https://a.com/2")      # same host: waits 0.05..0.15s
    assert time.monotonic() - started >= 0.05
