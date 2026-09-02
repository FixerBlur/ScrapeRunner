from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from scraperunner.config import ScrapeConfig
from scraperunner.crawler import Crawler
from scraperunner.downloader import ImageDownloader
from scraperunner.exporter import (
    export_items_csv,
    export_items_json,
    export_items_xlsx,
    export_links_csv,
    export_pages_json,
    unique_images,
    unique_item_images,
)
from scraperunner.fetcher import create_fetcher
from scraperunner.http import build_client
from scraperunner.models import PageResult
from scraperunner.utils.robots import RobotsCache

log = logging.getLogger(__name__)

PageHook = Callable[[PageResult], None]
ImageHook = Callable[[str, Path | None], None]
StopCheck = Callable[[], bool]


@dataclass
class CrawlReport:
    pages: list[PageResult]
    images: list[str]
    downloaded: dict[str, Path] = field(default_factory=dict)

    @property
    def total_links(self) -> int:
        return sum(len(page.links) for page in self.pages)

    @property
    def total_items(self) -> int:
        return sum(len(page.items) for page in self.pages)

    @property
    def failed(self) -> int:
        return sum(1 for page in self.pages if page.error)


def run_crawl(
    config: ScrapeConfig,
    *,
    on_page: PageHook | None = None,
    on_image: ImageHook | None = None,
    should_stop: StopCheck | None = None,
) -> CrawlReport:
    """Crawl, export JSON/CSV, optionally download images. Shared by CLI and web."""
    should_stop = should_stop or (lambda: False)
    pages: list[PageResult] = []

    with build_client(config) as client, create_fetcher(config, client) as fetcher:
        robots = RobotsCache(client, config.user_agent) if config.respect_robots else None
        for page in Crawler(config, fetcher, robots).crawl():
            pages.append(page)
            if on_page:
                on_page(page)
            if should_stop():
                log.info("Crawl stopped by request")
                break

        images = unique_images(pages)
        out = config.output_dir
        export_pages_json(pages, out / "pages.json")
        export_links_csv(pages, out / "links.csv")
        export_items_json(pages, out / "items.json")
        export_items_csv(pages, out / "items.csv")
        export_items_xlsx(pages, out / "items.xlsx")

        downloaded: dict[str, Path] = {}
        if config.download_images:
            # On listing pages only the card photos matter, not logos and banners.
            downloader = ImageDownloader(client, out / "images")
            for url in unique_item_images(pages) or images:
                if should_stop():
                    break
                path = downloader.download(url)
                if path is not None:
                    downloaded[url] = path
                if on_image:
                    on_image(url, path)

    return CrawlReport(pages=pages, images=images, downloaded=downloaded)
