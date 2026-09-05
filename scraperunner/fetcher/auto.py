from __future__ import annotations

import logging
import threading

import httpx
from bs4 import BeautifulSoup

from scraperunner.config import ScrapeConfig
from scraperunner.fetcher.base import Fetcher
from scraperunner.fetcher.http import HttpFetcher
from scraperunner.models import FetchResult
from scraperunner.parser.text import extract_text

log = logging.getLogger(__name__)

# A page below either threshold is treated as "probably JS-rendered":
# almost no links, or almost no visible text once boilerplate is stripped.
_MIN_ANCHORS = 3
_MIN_TEXT_CHARS = 300


def looks_js_rendered(soup: BeautifulSoup) -> bool:
    """Heuristic: does this page look like an empty shell waiting for JS?"""
    anchors = len(soup.find_all("a"))
    return anchors < _MIN_ANCHORS or len(extract_text(soup)) < _MIN_TEXT_CHARS


class AutoFetcher(Fetcher):
    """HTTP first; falls back to the browser when the HTML looks empty."""

    def __init__(self, config: ScrapeConfig, client: httpx.Client) -> None:
        self._config = config
        self._http = HttpFetcher(client, config.retries)
        self._browser: Fetcher | None = None
        self._browser_unavailable = False
        self._lock = threading.Lock()

    def fetch(self, url: str) -> FetchResult:
        result = self._http.fetch(url)
        if result.status == 200 and result.is_html and looks_js_rendered(result.soup):
            browser = self._get_browser()
            if browser is not None:
                log.info("Page looks JS-rendered, retrying with browser: %s", url)
                return browser.fetch(url)
        return result

    def _get_browser(self) -> Fetcher | None:
        with self._lock:
            if self._browser is None and not self._browser_unavailable:
                try:
                    from scraperunner.fetcher.browser import BrowserFetcher

                    self._browser = BrowserFetcher(self._config)
                except RuntimeError as exc:
                    log.warning("%s", exc)
                    self._browser_unavailable = True
            return self._browser

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
