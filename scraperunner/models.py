from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class FetchResult:
    """Raw response of a single fetch."""

    url: str
    final_url: str
    status: int
    html: str
    content_type: str = ""

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type or not self.content_type


@dataclass
class Item:
    """One card from a listing page: a product, an article, an ad."""

    title: str | None
    link: str | None
    image: str | None
    price: str | None
    old_price: str | None
    text: str
    group: int = 1  # which repeated-card group on the page it came from


@dataclass
class PageResult:
    """Everything extracted from one page."""

    url: str
    status: int
    title: str = ""
    depth: int = 0
    links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    text: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PageResult":
        data = dict(data)
        data["items"] = [Item(**item) for item in data.get("items", [])]
        return cls(**data)
