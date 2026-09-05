from __future__ import annotations

from bs4 import BeautifulSoup, Comment

# Tags that carry no article content: code, styling and site chrome.
_BOILERPLATE = ["script", "style", "noscript", "template", "header", "footer", "nav", "aside"]


def extract_text(soup: BeautifulSoup) -> str:
    """Readable page text, one block per line, with boilerplate skipped. Leaves the soup untouched."""
    lines = []
    for node in soup.find_all(string=True):
        if isinstance(node, Comment) or node.find_parent(_BOILERPLATE) is not None:
            continue
        text = " ".join(node.split())
        if text:
            lines.append(text)
    return "\n".join(lines)
