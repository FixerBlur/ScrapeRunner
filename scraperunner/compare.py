from __future__ import annotations

from dataclasses import asdict, dataclass, field

from scraperunner.models import Item
from scraperunner.parser.prices import parse_amount


@dataclass
class PriceChange:
    title: str | None
    link: str
    image: str | None
    before: str | None
    after: str | None
    delta_pct: float | None


@dataclass
class Changes:
    """What differs between two item lists of the same listing, matched by link."""

    added: list[Item] = field(default_factory=list)
    removed: list[Item] = field(default_factory=list)
    price_changes: list[PriceChange] = field(default_factory=list)
    unchanged: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def compare_items(before: list[Item], after: list[Item]) -> Changes:
    old = {item.link: item for item in before if item.link}
    new = {item.link: item for item in after if item.link}
    changes = Changes(
        added=[item for link, item in new.items() if link not in old],
        removed=[item for link, item in old.items() if link not in new],
    )
    for link, item in new.items():
        if link not in old:
            continue
        previous = old[link].price
        if (previous or "") == (item.price or ""):
            changes.unchanged += 1
        else:
            changes.price_changes.append(PriceChange(
                title=item.title, link=link, image=item.image,
                before=previous, after=item.price, delta_pct=_delta(previous, item.price),
            ))
    return changes


def _delta(before: str | None, after: str | None) -> float | None:
    if not before or not after:
        return None
    was, now = parse_amount(before), parse_amount(after)
    return round((now - was) / was * 100, 1) if was else None
