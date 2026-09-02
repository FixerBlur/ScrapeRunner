from __future__ import annotations

from collections import defaultdict

from bs4 import BeautifulSoup, Tag
from soupsieve import SelectorSyntaxError

from scraperunner.config import Selectors
from scraperunner.models import Item
from scraperunner.parser.images import image_sources
from scraperunner.parser.prices import card_prices, clean_price
from scraperunner.utils.url import normalize_url

# Fewer repeated blocks than this is a layout, not a listing.
_MIN_CARDS = 3
_MAX_TITLE = 200
_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def extract_items(soup: BeautifulSoup, base_url: str, selectors: Selectors = Selectors()) -> list[Item]:
    """Products, articles, listings: every group of repeated cards on the page.

    A card is a block that contains both a link and an image. Siblings with the
    same tag and classes form a group; every group of three or more counts,
    nested duplicates excluded. ``selectors.card`` replaces the detection with
    an explicit CSS selector; field selectors override individual fields.
    """
    groups = [soup.select(selectors.card)] if selectors.card else _card_groups(soup)
    items: list[Item] = []
    seen: set[str] = set()
    for group_number, cards in enumerate(groups, start=1):
        for card in cards:
            item = _parse_card(card, base_url, selectors, group_number)
            if item.link and item.link not in seen:
                seen.add(item.link)
                items.append(item)
    return items


def validate_selectors(selectors: Selectors) -> None:
    """Raise ``ValueError`` naming the first CSS selector that does not parse."""
    probe = BeautifulSoup("<div></div>", "lxml")
    for name, selector in vars(selectors).items():
        if selector:
            try:
                probe.select(selector)
            except SelectorSyntaxError as exc:
                raise ValueError(f"Invalid {name} selector {selector!r}: {exc}") from None


# --- card detection -----------------------------------------------------------

def _card_groups(soup: BeautifulSoup) -> list[list[Tag]]:
    """Repeated-card groups in document order. Bigger groups win over nested ones."""
    candidates: list[list[Tag]] = []
    for parent in soup.find_all(True):
        siblings: dict[tuple, list[Tag]] = defaultdict(list)
        for child in parent.find_all(True, recursive=False):
            siblings[_signature(child)].append(child)
        candidates.extend(m for m in siblings.values() if len(m) >= _MIN_CARDS and all(map(_is_card, m)))

    accepted: list[list[Tag]] = []
    taken: list[Tag] = []
    for members in sorted(candidates, key=len, reverse=True):
        if not any(_nested(member, other) for member in members for other in taken):
            accepted.append(members)
            taken.extend(members)

    position = {id(tag): index for index, tag in enumerate(soup.find_all(True))}
    accepted.sort(key=lambda group: position[id(group[0])])
    return accepted


def _signature(tag: Tag) -> tuple:
    return tag.name, tuple(sorted(tag.get("class", [])))


def _is_card(tag: Tag) -> bool:
    return tag.find("a", href=True) is not None and tag.find("img") is not None


def _nested(a: Tag, b: Tag) -> bool:
    return a is b or a in b.parents or b in a.parents


# --- fields -------------------------------------------------------------------

def _parse_card(card: Tag, base_url: str, selectors: Selectors, group: int) -> Item:
    """One card to one item. Every field uses its selector if given, the heuristic otherwise."""
    title_tag = None if selectors.title else _title_tag(card)
    price, old_price = _prices(card, selectors)
    return Item(
        title=_text_of(card, selectors.title) if selectors.title else _title_text(title_tag, card),
        link=_link(card, selectors.link, title_tag, base_url),
        image=_image(card, selectors.image, base_url),
        price=price,
        old_price=old_price,
        text=" ".join(card.get_text(" ").split()),
        group=group,
    )


def _prices(card: Tag, selectors: Selectors) -> tuple[str | None, str | None]:
    price = old_price = None
    if not (selectors.price and selectors.old_price):
        price, old_price = card_prices(card)
    if selectors.price:
        price = clean_price(_text_of(card, selectors.price))
    if selectors.old_price:
        old_price = clean_price(_text_of(card, selectors.old_price))
    return price, old_price


def _text_of(card: Tag, selector: str) -> str | None:
    tag = card.select_one(selector)
    return " ".join(tag.get_text(" ").split()) if tag else None


def _link(card: Tag, selector: str | None, title_tag: Tag | None, base_url: str) -> str | None:
    if selector:
        tag = card.select_one(selector)
        href = tag.get("href") if tag else None
    else:
        anchor = _anchor_for(card, title_tag)
        href = anchor["href"] if anchor else None
    return normalize_url(href, base_url) if href else None


def _image(card: Tag, selector: str | None, base_url: str) -> str | None:
    tag = card.select_one(selector) if selector else card.find("img")
    candidates = image_sources(tag) + ([tag["href"]] if tag is not None and tag.get("href") else [])
    return next((url for source in candidates if (url := normalize_url(source, base_url))), None)


def _title_tag(card: Tag) -> Tag | None:
    for names in (_HEADINGS, ("a",)):
        for tag in card.find_all(names):
            if len(tag.get_text(" ", strip=True)) >= 4:
                return tag
    return None


def _title_text(title_tag: Tag | None, card: Tag) -> str | None:
    if title_tag is not None:
        return title_tag.get_text(" ", strip=True)[:_MAX_TITLE]
    image = card.find("img", alt=True)
    return image["alt"].strip() or None if image else None


def _anchor_for(card: Tag, title_tag: Tag | None) -> Tag | None:
    """The link belonging to the title, falling back to the card's first link."""
    if title_tag is not None:
        if title_tag.name == "a" and title_tag.get("href"):
            return title_tag
        return title_tag.find("a", href=True) or title_tag.find_parent("a", href=True) or card.find("a", href=True)
    return card.find("a", href=True)
