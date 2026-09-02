from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

PLACEHOLDER = "{page}"
_RANGE_PART = re.compile(r"^(\d+)(?:-(\d+))?$")


def parse_page_range(spec: str) -> list[int]:
    """``"1-3,7"`` -> ``[1, 2, 3, 7]``. Raises ``ValueError`` on bad input."""
    pages: set[int] = set()
    for part in spec.split(","):
        match = _RANGE_PART.match(part.strip())
        if not match:
            raise ValueError(f"Invalid page range: {spec!r} (expected e.g. '1-5' or '1,3,5')")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if end < start:
            raise ValueError(f"Invalid page range: {part!r} (end before start)")
        pages.update(range(start, end + 1))
    return sorted(pages)


def detect_page_pattern(url: str) -> str | None:
    """Replace the page number in *url* with ``{page}``.

    Checks query parameters first (``?page=2``), then the last numeric
    path segment (``/catalog/2/``). Returns ``None`` if nothing numeric is found.
    """
    parsed = urlparse(url)

    query = parse_qsl(parsed.query, keep_blank_values=True)
    for index, (key, value) in enumerate(query):
        if value.isdigit():
            query[index] = (key, PLACEHOLDER)
            return urlunparse(parsed._replace(query=urlencode(query, safe="{}")))

    segments = parsed.path.split("/")
    for index in range(len(segments) - 1, -1, -1):
        if segments[index].isdigit():
            segments[index] = PLACEHOLDER
            return urlunparse(parsed._replace(path="/".join(segments)))

    return None


def paginated_urls(url: str, spec: str, pattern: str | None = None) -> list[str]:
    """Expand *url* into one URL per page in *spec* using *pattern* (or a detected one).

    A pattern without ``{page}`` is treated as a real page address the user
    pasted (``...?p=2``), and the number in it becomes the placeholder.
    """
    source = pattern or url
    if pattern is None or PLACEHOLDER not in pattern:
        pattern = detect_page_pattern(source)
    if pattern is None:
        raise ValueError(
            f"Cannot find a page number in {source!r}; use a URL with a page number "
            f"or a pattern containing {PLACEHOLDER}"
        )
    return [pattern.replace(PLACEHOLDER, str(number)) for number in parse_page_range(spec)]
