from __future__ import annotations

from bs4 import BeautifulSoup

from scraperunner.config import Selectors
from scraperunner.models import FetchResult, PageResult
from scraperunner.parser.images import extract_images
from scraperunner.parser.items import extract_items
from scraperunner.parser.links import extract_links
from scraperunner.parser.text import extract_text


def parse_page(
    fetched: FetchResult, depth: int = 0, with_text: bool = False, selectors: Selectors = Selectors()
) -> PageResult:
    """Turn raw HTML into a structured :class:`PageResult`."""
    soup = BeautifulSoup(fetched.html, "lxml")
    base_url = _resolve_base(soup, fetched.final_url)
    page = PageResult(
        url=fetched.final_url,
        status=fetched.status,
        title=soup.title.get_text(strip=True) if soup.title else "",
        depth=depth,
        links=extract_links(soup, base_url),
        images=extract_images(soup, base_url),
        items=extract_items(soup, base_url, selectors),
    )
    if with_text:
        page.text = extract_text(soup)  # last: it strips tags from the soup
    return page


def _resolve_base(soup: BeautifulSoup, fallback: str) -> str:
    base_tag = soup.find("base", href=True)
    return base_tag["href"] if base_tag else fallback
