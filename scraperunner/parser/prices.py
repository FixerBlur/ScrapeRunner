from __future__ import annotations

import re

from bs4 import Tag

_CURRENCY = r"(?:₴|грн\.?|uah|\$|€|eur|usd|£|zł|₽|руб\.?)"
_NUMBER = r"\d{1,3}(?:[ \u00a0,.]\d{3})*(?:[.,]\d{1,2})?"
PRICE = re.compile(rf"(?:{_CURRENCY}\s*{_NUMBER}|{_NUMBER}\s*{_CURRENCY})", re.IGNORECASE)
# An element that is nothing but a price, optionally prefixed with "from".
_PRICE_ELEMENT = re.compile(rf"(?:від|from|ціна|price)?[:\s]*{PRICE.pattern}[.\s]*", re.IGNORECASE)
# Markup that marks a price as the previous one: <del>, <s>, or "old"-ish class names.
_STRIKE_TAGS = ("del", "s", "strike")
_OLD_CLASS = re.compile(r"(?:^|[-_])(?:old|was|regular|compare|strike|crossed|before)(?:$|[-_])", re.IGNORECASE)


def card_prices(card: Tag) -> tuple[str | None, str | None]:
    """(current price, previous price) of one listing card.

    A price is the innermost element whose whole text is a price, so "449" and
    "₴" split across spans still count, while "+4 ₴" bonuses and "-589 ₴"
    discounts do not. Struck-through markup marks the previous price; with two
    plain prices the higher one is treated as previous.
    """
    current: list[str] = []
    previous: list[str] = []
    for tag in _price_elements(card):
        bucket = previous if _is_struck(tag, card) else current
        bucket.append(clean_price(tag.get_text(" ")))
    if not current:
        # Price is loose text rather than its own element: scan the card, skipping known previous prices.
        found = (" ".join(match.split()) for match in PRICE.findall(card.get_text(" ")))
        current = [price for price in found if price not in previous]

    if not previous and len(dict.fromkeys(current)) >= 2:
        first, second = current[:2]
        return (second, first) if parse_amount(first) > parse_amount(second) else (first, second)
    return (current[0] if current else None), (previous[0] if previous else None)


def clean_price(text: str | None) -> str | None:
    """The price inside *text* with whitespace normalised, or the text itself if no price matches."""
    if not text:
        return None
    match = PRICE.search(text)
    return " ".join((match.group(0) if match else text).split())


def parse_amount(price: str) -> float:
    """``"1 299,50 ₴"`` -> ``1299.5``. Unparseable input gives ``0.0``."""
    digits = re.sub(r"[^\d.,]", "", price)
    if "," in digits and "." not in digits:
        digits = digits.replace(",", ".")
    parts = digits.split(".")
    if len(parts) > 2:  # thousands separators, not decimals
        digits = "".join(parts)
    try:
        return float(digits)
    except ValueError:
        return 0.0


def _price_elements(card: Tag) -> list[Tag]:
    matched = [tag for tag in card.find_all(True) if _PRICE_ELEMENT.fullmatch(" ".join(tag.get_text(" ").split()))]
    return [tag for tag in matched if not any(child in matched for child in tag.find_all(True))]


def _is_struck(tag: Tag, card: Tag) -> bool:
    """Is *tag*, or anything between it and the card, marked as a previous price?"""
    for ancestor in [tag, *tag.parents]:
        if ancestor.name in _STRIKE_TAGS or any(_OLD_CLASS.search(cls) for cls in ancestor.get("class", [])):
            return True
        if ancestor is card:
            break
    return False
