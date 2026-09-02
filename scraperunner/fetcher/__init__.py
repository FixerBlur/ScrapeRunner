from __future__ import annotations

import httpx

from scraperunner.config import FetchMode, ScrapeConfig
from scraperunner.fetcher.base import Fetcher


def create_fetcher(config: ScrapeConfig, client: httpx.Client) -> Fetcher:
    """Factory: pick a fetcher implementation for the requested mode."""
    if config.mode is FetchMode.HTTP:
        from scraperunner.fetcher.http import HttpFetcher

        return HttpFetcher(client, config.retries)
    if config.mode is FetchMode.BROWSER:
        from scraperunner.fetcher.browser import BrowserFetcher

        return BrowserFetcher(config)

    from scraperunner.fetcher.auto import AutoFetcher

    return AutoFetcher(config, client)


__all__ = ["Fetcher", "create_fetcher"]
