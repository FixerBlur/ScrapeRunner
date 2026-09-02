from bs4 import BeautifulSoup

from scraperunner.models import FetchResult
from scraperunner.parser import extract_text, parse_page

HTML = """
<html><head><title>T</title><style>p{}</style><script>var x=1;</script></head>
<body>
  <nav><a href="/">Menu item</a></nav>
  <!-- hidden comment -->
  <h1>Headline</h1>
  <p>First   paragraph.</p>
  <footer>Copyright</footer>
</body></html>
"""


def test_boilerplate_is_removed_and_lines_are_clean():
    text = extract_text(BeautifulSoup(HTML, "lxml"))
    assert text == "T\nHeadline\nFirst paragraph."


def test_parse_page_keeps_links_even_when_text_is_extracted():
    fetched = FetchResult(url="https://s.com/", final_url="https://s.com/", status=200, html=HTML)
    page = parse_page(fetched, with_text=True)
    assert page.links == ["https://s.com/"]
    assert "Headline" in page.text


def test_text_is_off_by_default():
    fetched = FetchResult(url="https://s.com/", final_url="https://s.com/", status=200, html=HTML)
    assert parse_page(fetched).text is None
