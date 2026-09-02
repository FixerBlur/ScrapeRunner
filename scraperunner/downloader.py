from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

import httpx

from scraperunner.utils.url import url_to_filename

log = logging.getLogger(__name__)


class ImageDownloader:
    """Saves image URLs into a folder, skipping non-images and files already present."""

    def __init__(self, client: httpx.Client, output_dir: Path) -> None:
        self._client = client
        self._dir = output_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def download(self, url: str) -> Path | None:
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Image download failed %s: %s", url, exc)
            return None

        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if not content_type.startswith("image/"):
            log.debug("Skipping non-image %s (%s)", url, content_type)
            return None

        extension = mimetypes.guess_extension(content_type) or ".bin"
        path = self._dir / url_to_filename(url, extension)
        if not path.exists():
            path.write_bytes(response.content)
            log.info("Saved %s", path.name)
        return path
