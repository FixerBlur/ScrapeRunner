from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)


class RobotsCache:
    """Fetches and caches robots.txt per origin."""

    def __init__(self, client: httpx.Client, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    def can_fetch(self, url: str) -> bool:
        parser = self._parser_for(url)
        return parser is None or parser.can_fetch(self._user_agent, url)

    def _parser_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._parsers:
            self._parsers[origin] = self._load(origin)
        return self._parsers[origin]

    def _load(self, origin: str) -> RobotFileParser | None:
        try:
            response = self._client.get(f"{origin}/robots.txt")
        except httpx.HTTPError as exc:
            log.debug("robots.txt unavailable for %s: %s", origin, exc)
            return None
        if response.status_code != 200:
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser
