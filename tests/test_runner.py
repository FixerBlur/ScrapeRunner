from pathlib import Path

import pytest

from scraperunner import runner
from scraperunner.config import FetchMode, ScrapeConfig
from scraperunner.fetcher.base import Fetcher
from scraperunner.models import FetchResult

SITE = {
    "https://s.com/": '<a href="/a">a</a><a href="/b">b</a><img src="/i.png">',
    "https://s.com/a": "<p>a</p>",
    "https://s.com/b": "<p>b</p>",
}


class FakeFetcher(Fetcher):
    def fetch(self, url: str) -> FetchResult:
        return FetchResult(url=url, final_url=url, status=200, html=SITE[url], content_type="text/html")


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ScrapeConfig:
    monkeypatch.setattr(runner, "create_fetcher", lambda config, client: FakeFetcher())
    return ScrapeConfig(
        start_url="https://s.com/", depth=1, delay=0, respect_robots=False,
        mode=FetchMode.HTTP, output_dir=tmp_path,
    )


def test_run_crawl_exports_and_reports(config: ScrapeConfig):
    seen = []
    report = runner.run_crawl(config, on_page=seen.append)

    assert sorted(page.url for page in seen) == sorted(SITE)
    assert seen[0].url == "https://s.com/"  # the seed always completes first
    assert report.stats.pages == 3 and report.stats.links == 2 and report.stats.failed == 0
    assert report.images == ["https://s.com/i.png"]
    for name in ("pages.json", "links.csv", "items.json", "items.csv", "items.xlsx"):
        assert (config.output_dir / name).exists()


def test_run_crawl_stops_when_asked(config: ScrapeConfig):
    report = runner.run_crawl(config, should_stop=lambda: True)
    assert report.stats.pages == 0
    assert (config.output_dir / "pages.json").exists()  # exports are still valid
