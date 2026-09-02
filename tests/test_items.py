from bs4 import BeautifulSoup

from scraperunner.config import Selectors
from scraperunner.parser.items import extract_items, validate_selectors
import pytest

BASE = "https://shop.com/"

CATALOG = """
<html><body>
<header><a href="/"><img src="/logo.png"></a></header>
<ul class="menu"><li><a href="/a">A</a></li><li><a href="/b">B</a></li><li><a href="/c">C</a></li></ul>
<div class="grid">
  <div class="tile"><a href="/p/1"><img data-src="/img/1.jpg" alt="Pan one"></a><h3><a href="/p/1">Frying pan Berlin 28 cm</a></h3><span class="old">1 599 ₴</span><span>1 299 ₴</span></div>
  <div class="tile"><a href="/p/2"><img src="/img/2.jpg"></a><h3><a href="/p/2">Wok pan 30 cm</a></h3><span>899 грн</span></div>
  <div class="tile"><a href="/p/3"><img srcset="/img/3-1x.jpg 1x, /img/3-2x.jpg 2x"></a><h3><a href="/p/3">Grill pan</a></h3><span>$ 24.99</span></div>
  <div class="tile"><a href="/p/3"><img src="/img/3.jpg"></a><h3><a href="/p/3">Grill pan duplicate</a></h3></div>
  <div class="banner"><img src="/promo.jpg"></div>
</div>
</body></html>
"""


def items_of(html):
    return extract_items(BeautifulSoup(html, "lxml"), BASE)


def test_largest_repeated_card_group_becomes_items():
    items = items_of(CATALOG)
    assert [item.link for item in items] == ["https://shop.com/p/1", "https://shop.com/p/2", "https://shop.com/p/3"]


def test_fields_are_parsed_from_each_card():
    first, second, third = items_of(CATALOG)
    assert first.title == "Frying pan Berlin 28 cm"
    assert first.image == "https://shop.com/img/1.jpg"       # lazy data-src
    assert first.price == "1 299 ₴"
    assert first.old_price == "1 599 ₴"     # class="old" marks the previous price
    assert second.price == "899 грн"
    assert second.old_price is None
    assert third.image == "https://shop.com/img/3-1x.jpg"    # srcset
    assert third.price == "$ 24.99"


def test_menu_links_without_images_are_not_items():
    assert all("/p/" in item.link for item in items_of(CATALOG))


def test_plain_page_has_no_items():
    assert items_of("<html><body><h1>About us</h1><p>text</p><a href='/x'><img src='/y.png'></a></body></html>") == []


def test_title_falls_back_to_image_alt():
    html = "<div>" + "".join(f'<div class="c"><a href="/i/{n}"><img src="/i/{n}.jpg" alt="Item {n}"></a></div>' for n in range(3)) + "</div>"
    assert [item.title for item in items_of(html)] == ["Item 0", "Item 1", "Item 2"]


def cards(*bodies):
    return "<div>" + "".join(f'<div class="c"><a href="/i/{n}"><img src="/i.jpg"></a>{body}</div>' for n, body in enumerate(bodies)) + "</div>"


def test_struck_through_price_is_old_price():
    html = cards("<del>2 000 ₴</del> <b>1 500 ₴</b>", "<s>$ 30</s> $ 20", "<span class='price-old'>10 €</span><span>8 €</span>")
    assert [(i.price, i.old_price) for i in items_of(html)] == [("1 500 ₴", "2 000 ₴"), ("$ 20", "$ 30"), ("8 €", "10 €")]


def test_two_plain_prices_higher_one_is_old():
    html = cards("999 ₴ 1 299 ₴", "1 299 ₴ 999 ₴", "500 ₴")
    assert [(i.price, i.old_price) for i in items_of(html)] == [("999 ₴", "1 299 ₴"), ("999 ₴", "1 299 ₴"), ("500 ₴", None)]


def test_split_price_nodes_bonuses_and_discounts():
    body = (
        '<div class="price-old"><span>1 038 ₴</span><span>-589 ₴</span></div>'
        '<div class="price-current"><span>449</span> <span>₴</span></div>'
        '<div class="bonus">+4 ₴</div>'
    )
    item = items_of(cards(body, body, body))[0]
    assert (item.price, item.old_price) == ("449 ₴", "1 038 ₴")


TWO_LISTINGS = """
<div class="sale">
  <div class="s"><a href="/s/1"><img src="/1.jpg"></a><h3>Sale one</h3></div>
  <div class="s"><a href="/s/2"><img src="/2.jpg"></a><h3>Sale two</h3></div>
  <div class="s"><a href="/s/3"><img src="/3.jpg"></a><h3>Sale three</h3></div>
</div>
<ul class="new">
  <li class="n"><div class="inner"><a href="/n/1"><img src="/4.jpg"></a><h3>New one</h3></div></li>
  <li class="n"><div class="inner"><a href="/n/2"><img src="/5.jpg"></a><h3>New two</h3></div></li>
  <li class="n"><div class="inner"><a href="/n/3"><img src="/6.jpg"></a><h3>New three</h3></div></li>
  <li class="n"><div class="inner"><a href="/n/4"><img src="/7.jpg"></a><h3>New four</h3></div></li>
</ul>
"""


def test_every_repeated_group_is_kept_and_numbered_in_document_order():
    items = items_of(TWO_LISTINGS)
    assert [(item.title, item.group) for item in items] == [
        ("Sale one", 1), ("Sale two", 1), ("Sale three", 1),
        ("New one", 2), ("New two", 2), ("New three", 2), ("New four", 2),
    ]


def test_nested_wrappers_do_not_duplicate_a_group():
    items = items_of(TWO_LISTINGS)
    assert len(items) == 7 and len({item.link for item in items}) == 7


def test_custom_card_selector_replaces_detection():
    html = '<div><p class="row"><a href="/x/1"><img src="/a.jpg"></a><em>Alpha</em><i>10 ₴</i></p></div>'
    selectors = Selectors(card="p.row", title="em", price="i", link="a", image="img")
    (item,) = extract_items(BeautifulSoup(html, "lxml"), BASE, selectors)
    assert (item.title, item.price, item.link, item.image) == ("Alpha", "10 ₴", "https://shop.com/x/1", "https://shop.com/a.jpg")


def test_field_selectors_override_only_their_field():
    body = '<h3>Heuristic title</h3><span class="brand">Krauff</span><span>100 ₴</span>'
    html = cards(body, body, body)
    items = extract_items(BeautifulSoup(html, "lxml"), BASE, Selectors(title=".brand"))
    assert items[0].title == "Krauff"
    assert items[0].price == "100 ₴"


def test_invalid_selector_is_reported_by_name():
    with pytest.raises(ValueError, match="price selector"):
        validate_selectors(Selectors(price="div[[["))
