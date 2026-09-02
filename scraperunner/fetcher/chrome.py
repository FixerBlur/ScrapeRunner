from __future__ import annotations

import hashlib
import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
import httpx

log = logging.getLogger(__name__)

DEFAULT_PORT = 9222
DEFAULT_CDP_URL = f"http://127.0.0.1:{DEFAULT_PORT}"
PROFILE_NAME = "scraperunner-chrome"
_STARTUP_TIMEOUT = 20.0
_EXECUTABLE_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def find_chrome() -> Path | None:
    """Locate a Chrome/Chromium executable on this machine."""
    for candidate in _known_locations():
        if candidate.is_file():
            return candidate
    for name in _EXECUTABLE_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def profile_dir() -> Path:
    """A dedicated profile: Chrome refuses remote debugging on the default one."""
    base = os.environ.get("LOCALAPPDATA") or Path.home() / ".cache"
    return Path(base) / PROFILE_NAME


def is_running(cdp_url: str) -> bool:
    try:
        return httpx.get(f"{cdp_url}/json/version", timeout=1.0).status_code == 200
    except httpx.HTTPError:
        return False


def ensure_chrome(proxy: str | None = None) -> str:
    """Return the CDP URL of a running Chrome, launching a visible one if needed.

    A Chrome started here is left running so later crawls reuse it and keep
    whatever bot checks or logins the user has already passed in it. Each
    proxy gets its own profile and port, so a proxied crawl never silently
    reuses a direct-connection Chrome.
    """
    port, profile = chrome_slot(proxy)
    cdp_url = f"http://127.0.0.1:{port}"
    if is_running(cdp_url):
        return cdp_url

    chrome = find_chrome()
    if chrome is None:
        raise RuntimeError(
            "Google Chrome not found. Install it, or start a browser yourself and pass --cdp"
        )

    command = [
        str(chrome),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if proxy:
        command.append(f"--proxy-server={proxy}")
    command.append("about:blank")

    log.info("Launching Chrome: %s", chrome)
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    deadline = time.monotonic() + _STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if is_running(cdp_url):
            return cdp_url
        time.sleep(0.25)
    raise RuntimeError(f"Chrome started but {cdp_url} did not answer within {_STARTUP_TIMEOUT:.0f}s")


def chrome_slot(proxy: str | None) -> tuple[int, Path]:
    """(debug port, profile folder) for a proxy setting; the default slot without one."""
    if not proxy:
        return DEFAULT_PORT, profile_dir()
    digest = hashlib.sha1(proxy.encode()).hexdigest()
    return 9300 + int(digest[:4], 16) % 100, profile_dir().with_name(f"{PROFILE_NAME}-{digest[:8]}")


def _known_locations() -> list[Path]:
    system = platform.system()
    if system == "Windows":
        roots = (os.environ.get(name) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"))
        return [Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe" for root in roots if root]
    if system == "Darwin":
        return [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    return []
