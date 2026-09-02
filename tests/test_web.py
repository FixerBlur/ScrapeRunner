import pytest

pytest.importorskip("fastapi")

from scraperunner.config import FetchMode
from scraperunner.web.app import JobRequest


def test_request_maps_onto_config():
    request = JobRequest(url="https://s.com", depth=2, mode="browser", pages=" 1-3 ", proxy="")
    config = request.to_config()
    assert config.start_url == "https://s.com"
    assert config.depth == 2
    assert config.mode is FetchMode.BROWSER
    assert config.pages == "1-3"
    assert config.proxy is None


def test_selectors_are_validated_and_mapped():
    request = JobRequest(url="https://s.com", selectors={"card": " div.p ", "price": ""})
    config = request.to_config()
    assert config.selectors.card == "div.p" and config.selectors.price is None
    with pytest.raises(ValueError, match="price selector"):
        JobRequest(url="https://s.com", selectors={"price": "div[[["})


def test_request_rejects_bad_depth():
    with pytest.raises(ValueError):
        JobRequest(url="https://s.com", depth=99)
