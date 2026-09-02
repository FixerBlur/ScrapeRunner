from pathlib import Path

from scraperunner.config import FetchMode, ScrapeConfig, Selectors


def test_config_round_trips_through_dict():
    config = ScrapeConfig(
        start_url="https://s.com", mode=FetchMode.BROWSER, output_dir=Path("out/x"),
        selectors=Selectors(card="div.p", price=".price"), pages="1-3", concurrency=2,
    )
    restored = ScrapeConfig.from_dict(config.to_dict())
    assert restored == config
    assert restored.selectors.card == "div.p"
    assert Selectors().is_empty and not restored.selectors.is_empty
