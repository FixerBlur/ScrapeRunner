from pathlib import Path

import httpx

from scraperunner.downloader import ImageDownloader

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def client_for(routes):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        status, content_type, body = routes[str(request.url)]
        return httpx.Response(status, content=body, headers={"content-type": content_type})

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_images_are_saved_with_extension_and_reused(tmp_path: Path):
    client, calls = client_for({"https://s.com/a.png": (200, "image/png", PNG)})
    downloader = ImageDownloader(client, tmp_path)
    first = downloader.download("https://s.com/a.png")
    second = downloader.download("https://s.com/a.png")
    assert first == second and first.suffix == ".png" and first.read_bytes() == PNG
    assert len(calls) == 2  # fetched again, but not rewritten


def test_non_images_and_errors_are_skipped(tmp_path: Path):
    client, _ = client_for({
        "https://s.com/pixel": (200, "text/html", b"<html>tracking</html>"),
        "https://s.com/missing.jpg": (404, "image/jpeg", b""),
    })
    downloader = ImageDownloader(client, tmp_path)
    assert downloader.download("https://s.com/pixel") is None
    assert downloader.download("https://s.com/missing.jpg") is None
    assert list(tmp_path.iterdir()) == []
