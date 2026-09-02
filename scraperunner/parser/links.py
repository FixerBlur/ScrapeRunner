from __future__ import annotations

from bs4 import BeautifulSoup

from scraperunner.utils.url import normalize_url

_LINK_SELECTORS = ("a[href]", "area[href]")


def extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Return unique, absolute http(s) links in document order."""
    seen: set[str] = set()
    links: list[str] = []
    for selector in _LINK_SELECTORS:
        for tag in soup.select(selector):
            url = normalize_url(tag.get("href", ""), base_url)
            if url and url not in seen:
                seen.add(url)
                links.append(url)
    return links
