from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class FetchMode(str, Enum):
    HTTP = "http"          # plain HTTP request, fast
    BROWSER = "browser"    # real Google Chrome over DevTools protocol
    AUTO = "auto"          # HTTP first, Chrome fallback for empty pages


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 ScrapeRunner/0.1"
)


@dataclass(frozen=True)
class Selectors:
    """Optional CSS selectors that override item detection. Unset fields use the heuristic."""

    card: str | None = None
    title: str | None = None
    price: str | None = None
    old_price: str | None = None
    link: str | None = None
    image: str | None = None

    @property
    def is_empty(self) -> bool:
        return not any(asdict(self).values())


@dataclass(frozen=True)
class ScrapeConfig:
    """All knobs for a single crawl run."""

    start_url: str
    # Crawl limits
    depth: int = 1
    max_pages: int = 100
    same_domain: bool = True
    respect_robots: bool = True
    # Pagination: expand start_url into "page 1..N" seeds
    pages: str | None = None          # e.g. "1-5" or "1,3,7"
    page_pattern: str | None = None   # URL template with {page}; auto-detected if omitted
    # Networking
    delay: float = 0.5                # minimum gap between requests to one host, jittered
    timeout: float = 15.0
    retries: int = 2                  # extra attempts on network errors and 5xx/429
    concurrency: int = 4              # pages fetched in parallel
    proxy: str | None = None
    user_agent: str = DEFAULT_USER_AGENT
    # Browser
    mode: FetchMode = FetchMode.AUTO
    settle: float = 1.5               # seconds to let JS run after DOM is ready
    cdp_url: str | None = None        # attach to a running Chrome instead of launching one
    # Extraction
    selectors: Selectors = Selectors()
    extract_text: bool = False
    # Output
    download_images: bool = False
    output_dir: Path = Path("results")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["mode"] = self.mode.value
        data["output_dir"] = str(self.output_dir)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ScrapeConfig":
        data = dict(data)
        data["mode"] = FetchMode(data.get("mode", FetchMode.AUTO))
        data["output_dir"] = Path(data.get("output_dir", "results"))
        data["selectors"] = Selectors(**(data.get("selectors") or {}))
        return cls(**data)
