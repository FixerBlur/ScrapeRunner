from __future__ import annotations

import queue
import threading
from concurrent.futures import Future

from scraperunner.config import ScrapeConfig
from scraperunner.fetcher.base import Fetcher
from scraperunner.fetcher.chrome import ensure_chrome
from scraperunner.models import FetchResult


class BrowserFetcher(Fetcher):
    """Real Google Chrome driven over the DevTools protocol.

    Sites see an ordinary browser with a persistent profile, so checks that
    block headless automation pass, and anything the user solved by hand in
    that window (a bot check, a login) stays solved. Chrome is launched on
    demand unless ``config.cdp_url`` points at one already running.

    Playwright's sync API is bound to one thread, so all browser work runs on
    a private thread and ``fetch`` may be called from any thread; requests are
    served one at a time.
    """

    def __init__(self, config: ScrapeConfig) -> None:
        self._config = config
        self._requests: queue.Queue[tuple[str, Future] | None] = queue.Queue()
        self._ready = threading.Event()
        self._startup_error: Exception | None = None
        self._thread = threading.Thread(target=self._serve, name="chrome", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._startup_error is not None:
            raise self._startup_error

    def fetch(self, url: str) -> FetchResult:
        future: Future = Future()
        self._requests.put((url, future))
        return future.result()

    def close(self) -> None:
        self._requests.put(None)
        self._thread.join(timeout=15)

    def _serve(self) -> None:
        try:
            session = _ChromeSession(self._config)
        except Exception as exc:
            self._startup_error = exc
            self._ready.set()
            return
        self._ready.set()
        try:
            while (request := self._requests.get()) is not None:
                url, future = request
                try:
                    future.set_result(session.fetch(url))
                except Exception as exc:
                    future.set_exception(RuntimeError(f"Browser fetch failed: {exc}"))
        finally:
            session.close()


class _ChromeSession:
    """The Playwright connection itself. Used only from the fetcher's thread."""

    def __init__(self, config: ScrapeConfig) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Browser mode requires the Playwright client: pip install playwright") from exc

        cdp_url = config.cdp_url or ensure_chrome(proxy=config.proxy)
        self._timeout_ms = int(config.timeout * 1000)
        self._settle_ms = int(config.settle * 1000)
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            self._playwright.stop()
            raise RuntimeError(
                f"Cannot reach Chrome at {cdp_url}. Start it with --remote-debugging-port "
                "and a separate --user-data-dir, or drop --cdp to let ScrapeRunner launch one"
            ) from exc
        contexts = self._browser.contexts
        self._context = contexts[0] if contexts else self._browser.new_context()

    def fetch(self, url: str) -> FetchResult:
        page = self._context.new_page()
        try:
            # "domcontentloaded" + a short settle beats "networkidle": sites with
            # analytics beacons never go idle and would time out instead.
            response = page.goto(url, timeout=self._timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(self._settle_ms)
            return FetchResult(
                url=url,
                final_url=page.url,
                status=response.status if response else 0,
                html=page.content(),
                content_type=response.headers.get("content-type", "text/html") if response else "text/html",
            )
        finally:
            page.close()

    def close(self) -> None:
        # Disconnects only: the Chrome window stays open for the next crawl.
        self._browser.close()
        self._playwright.stop()
