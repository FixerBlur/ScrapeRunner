from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from scraperunner.utils.url import normalize_url

# Attributes commonly used by lazy-loading libraries.
_SRC_ATTRIBUTES = ("src", "data-src", "data-lazy-src", "data-original", "data-url")
_SRCSET_ATTRIBUTES = ("srcset", "data-srcset")
_META_SELECTORS = (
    'meta[property="og:image"]',
    'meta[name="twitter:image"]',
    'link[rel="icon"]',
    'link[rel="apple-touch-icon"]',
)
_CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.IGNORECASE)


def extract_images(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Return unique, absolute image URLs found anywhere in the page."""
    seen: set[str] = set()
    images: list[str] = []

    def add(raw: str | None) -> None:
        url = normalize_url(raw or "", base_url)
        if url and url not in seen:
            seen.add(url)
            images.append(url)

    for tag in soup.find_all(["img", "source"]):
        for candidate in image_sources(tag):
            add(candidate)

    for selector in _META_SELECTORS:
        for tag in soup.select(selector):
            add(tag.get("content") or tag.get("href"))

    for tag in soup.find_all(style=True):
        for candidate in _CSS_URL.findall(tag["style"]):
            add(candidate)
    for style_tag in soup.find_all("style"):
        for candidate in _CSS_URL.findall(style_tag.get_text()):
            add(candidate)

    return images


def image_sources(tag: Tag | None) -> list[str]:
    """Raw URL candidates of one <img>/<source>, lazy-load attributes and srcset included."""
    if tag is None:
        return []
    sources = [tag[attribute] for attribute in _SRC_ATTRIBUTES if tag.get(attribute)]
    for attribute in _SRCSET_ATTRIBUTES:
        sources.extend(_parse_srcset(tag.get(attribute)))
    return sources


def _parse_srcset(value: str | None) -> list[str]:
    """``srcset="a.jpg 1x, b.jpg 2x"`` -> ``["a.jpg", "b.jpg"]``."""
    if not value:
        return []
    urls = []
    for part in value.split(","):
        candidate = part.strip().split()
        if candidate:
            urls.append(candidate[0])
    return urls
