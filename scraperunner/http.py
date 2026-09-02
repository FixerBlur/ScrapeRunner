from __future__ import annotations

import httpx

from scraperunner.config import ScrapeConfig


def build_client(config: ScrapeConfig) -> httpx.Client:
    """The single HTTP client shared by fetching, robots.txt and downloads."""
    return httpx.Client(
        headers={
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=config.timeout,
        follow_redirects=True,
        proxy=config.proxy,
    )
