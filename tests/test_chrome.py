import pytest

from scraperunner.fetcher import chrome


def test_running_chrome_is_reused(monkeypatch):
    monkeypatch.setattr(chrome, "is_running", lambda url: True)
    monkeypatch.setattr(chrome, "find_chrome", lambda: pytest.fail("must not try to launch"))
    assert chrome.ensure_chrome() == chrome.DEFAULT_CDP_URL


def test_missing_chrome_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(chrome, "is_running", lambda url: False)
    monkeypatch.setattr(chrome, "find_chrome", lambda: None)
    with pytest.raises(RuntimeError, match="not found"):
        chrome.ensure_chrome()


def test_profile_dir_is_not_the_default_profile():
    assert chrome.profile_dir().name == chrome.PROFILE_NAME


def test_each_proxy_gets_its_own_port_and_profile():
    default_port, default_profile = chrome.chrome_slot(None)
    port_a, profile_a = chrome.chrome_slot("http://proxy-a:8080")
    port_b, profile_b = chrome.chrome_slot("http://proxy-b:8080")
    assert default_port == chrome.DEFAULT_PORT
    assert port_a != default_port and profile_a != default_profile
    assert (port_a, profile_a) != (port_b, profile_b)
    assert chrome.chrome_slot("http://proxy-a:8080") == (port_a, profile_a)
