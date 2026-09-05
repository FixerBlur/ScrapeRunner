from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from scraperunner.config import ScrapeConfig
from scraperunner.crawler import Crawler
from scraperunner.downloader import ImageDownloader
from scraperunner.exporter import CrawlStats, ExportWriter, rows_to_items
from scraperunner.fetcher import create_fetcher
from scraperunner.http import build_client
from scraperunner.models import Item, PageResult
from scraperunner.utils.robots import RobotsCache

log = logging.getLogger(__name__)

PageHook = Callable[[PageResult], None]
ImageHook = Callable[[str, Path | None], None]
StopCheck = Callable[[], bool]


@dataclass
class CrawlReport:
    stats: CrawlStats
    item_rows: list[dict]
    images: list[str]
    downloaded: dict[str, Path] = field(default_factory=dict)

    @property
    def items(self) -> list[Item]:
        return rows_to_items(self.item_rows)


def run_crawl(
    config: ScrapeConfig,
    *,
    on_page: PageHook | None = None,
    on_image: ImageHook | None = None,
    should_stop: StopCheck | None = None,
) -> CrawlReport:
    """Crawl, export as pages arrive, optionally download images. Shared by CLI and web."""
    should_stop = should_stop or (lambda: False)

    with build_client(config) as client, create_fetcher(config, client) as fetcher, ExportWriter(config.output_dir) as writer:
        robots = RobotsCache(client, config.user_agent) if config.respect_robots else None
        for page in Crawler(config, fetcher, robots, should_stop).crawl():
            writer.add(page)
            if on_page:
                on_page(page)
        writer.close()  # items.* exist before downloads start

        downloaded: dict[str, Path] = {}
        if config.download_images:
            # On listing pages only the card photos matter, not logos and banners.
            downloader = ImageDownloader(client, config.output_dir / "images")
            for url in writer.item_images or writer.stats.images:
                if should_stop():
                    break
                path = downloader.download(url)
                if path is not None:
                    downloaded[url] = path
                if on_image:
                    on_image(url, path)

    return CrawlReport(stats=writer.stats, item_rows=writer.item_rows, images=writer.stats.images, downloaded=downloaded)
