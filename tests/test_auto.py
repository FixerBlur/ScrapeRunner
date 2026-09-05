import httpx
from bs4 import BeautifulSoup

from scraperunner.config import ScrapeConfig
from scraperunner.fetcher import browser as browser_module
from scraperunner.fetcher.auto import AutoFetcher, looks_js_rendered
from scraperunner.models import FetchResult

SHELL = """<html><body><div id="root"></div>
<a href="/">Home</a><a href="/login">Login</a><a href="/next">Next</a><a href="/x">X</a>
<script>window.data = [/* thousands of chars of JSON */ %s];</script>
</body></html>""" % ("1," * 2000)

CONTENT = "<html><body>" + "".join(
    f'<p>Paragraph number {i} with some readable text in it.</p><a href="/p/{i}">more</a>'
    for i in range(20)
) + "</body></html>"


def soup(html):
    return BeautifulSoup(html, "lxml")


def test_shell_page_with_big_script_is_detected():
    assert looks_js_rendered(soup(SHELL))


def test_content_page_is_not_flagged():
    assert not looks_js_rendered(soup(CONTENT))


class FakeBrowser:
    created = 0

    def __init__(self, config):
        FakeBrowser.created += 1

    def fetch(self, url):
        return FetchResult(url=url, final_url=url, status=200, html=CONTENT, content_type="text/html")

    def close(self):
        pass


def http_client(html):
    return httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"})
    ))


def test_shell_pages_fall_back_to_the_browser_once(monkeypatch):
    monkeypatch.setattr(browser_module, "BrowserFetcher", FakeBrowser)
    FakeBrowser.created = 0
    fetcher = AutoFetcher(ScrapeConfig(start_url="https://s.com/"), http_client(SHELL))
    assert "Paragraph" in fetcher.fetch("https://s.com/a").html
    assert "Paragraph" in fetcher.fetch("https://s.com/b").html
    assert FakeBrowser.created == 1


def test_content_pages_never_open_the_browser(monkeypatch):
    monkeypatch.setattr(browser_module, "BrowserFetcher", FakeBrowser)
    FakeBrowser.created = 0
    fetcher = AutoFetcher(ScrapeConfig(start_url="https://s.com/"), http_client(CONTENT))
    fetcher.fetch("https://s.com/a")
    assert FakeBrowser.created == 0


def test_missing_browser_keeps_http_result(monkeypatch):
    def unavailable(config):
        raise RuntimeError("no chrome")

    monkeypatch.setattr(browser_module, "BrowserFetcher", unavailable)
    fetcher = AutoFetcher(ScrapeConfig(start_url="https://s.com/"), http_client(SHELL))
    assert fetcher.fetch("https://s.com/a").html == SHELL
    assert fetcher.fetch("https://s.com/b").html == SHELL  # not retried every time
