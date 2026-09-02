from bs4 import BeautifulSoup

from scraperunner.models import FetchResult
from scraperunner.parser import extract_images, extract_links, parse_page

BASE = "https://example.com/"

HTML = """
<html>
<head>
  <title> Demo </title>
  <meta property="og:image" content="/og.png">
  <style>.hero { background-image: url("/css/hero.jpg"); }</style>
</head>
<body>
  <a href="/a">A</a>
  <a href="https://other.com/b#x">B</a>
  <a href="/a">duplicate</a>
  <a href="mailto:me@example.com">mail</a>
  <img src="/img/1.jpg">
  <img data-src="/img/lazy.jpg" srcset="/img/2x.jpg 2x, /img/1x.jpg 1x">
  <picture><source srcset="/img/webp.webp"></picture>
  <div style="background: url('/inline.png')"></div>
</body>
</html>
"""


def soup():
    return BeautifulSoup(HTML, "lxml")


def test_links_are_absolute_unique_and_clean():
    assert extract_links(soup(), BASE) == [
        "https://example.com/a",
        "https://other.com/b",
    ]


def test_images_from_all_sources():
    images = extract_images(soup(), BASE)
    expected = {
        "https://example.com/img/1.jpg",
        "https://example.com/img/lazy.jpg",
        "https://example.com/img/2x.jpg",
        "https://example.com/img/1x.jpg",
        "https://example.com/img/webp.webp",
        "https://example.com/og.png",
        "https://example.com/inline.png",
        "https://example.com/css/hero.jpg",
    }
    assert set(images) == expected
    assert len(images) == len(expected)


def test_parse_page_builds_result():
    fetched = FetchResult(url=BASE, final_url=BASE, status=200, html=HTML, content_type="text/html")
    page = parse_page(fetched, depth=2)
    assert page.title == "Demo"
    assert page.depth == 2
    assert page.status == 200
    assert "https://example.com/a" in page.links


def test_base_tag_is_respected():
    html = '<html><head><base href="https://cdn.example.com/x/"></head><body><a href="p">p</a></body></html>'
    fetched = FetchResult(url=BASE, final_url=BASE, status=200, html=html)
    assert parse_page(fetched).links == ["https://cdn.example.com/x/p"]
