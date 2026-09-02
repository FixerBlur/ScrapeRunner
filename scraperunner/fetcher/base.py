from __future__ import annotations

from abc import ABC, abstractmethod

from scraperunner.models import FetchResult


class Fetcher(ABC):
    """Downloads a page and returns its HTML."""

    @abstractmethod
    def fetch(self, url: str) -> FetchResult: ...

    def close(self) -> None:
        """Release underlying resources (connections, browser)."""

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
