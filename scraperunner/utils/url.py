from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

_ALLOWED_SCHEMES = {"http", "https"}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def normalize_url(href: str, base_url: str) -> str | None:
    """Resolve *href* against *base_url* and clean it up.

    Returns ``None`` for anything that is not a fetchable http(s) URL
    (mailto:, javascript:, data:, anchors, empty strings).
    """
    if not href:
        return None
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
        return None

    absolute = urljoin(base_url, href)
    absolute, _fragment = urldefrag(absolute)
    parsed = urlparse(absolute)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        return None

    cleaned = parsed._replace(netloc=parsed.netloc.lower())
    if cleaned.path == "":
        cleaned = cleaned._replace(path="/")
    return urlunparse(cleaned)


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def is_same_domain(url: str, other: str) -> bool:
    return domain_of(url) == domain_of(other)


def url_to_filename(url: str, extension: str = "") -> str:
    """Build a filesystem-safe, unique file name for a URL."""
    parsed = urlparse(url)
    stem = Path(parsed.path).stem or "file"
    stem = _SAFE_NAME.sub("_", stem)[:60]
    digest = hashlib.sha1(url.encode()).hexdigest()[:10]
    ext = extension or Path(parsed.path).suffix
    return f"{stem}_{digest}{ext}"
