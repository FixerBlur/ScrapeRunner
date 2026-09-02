from __future__ import annotations

from bs4 import BeautifulSoup, Comment

# Tags that carry no article content: code, styling and site chrome.
_BOILERPLATE = ("script", "style", "noscript", "template", "header", "footer", "nav", "aside")


def extract_text(soup: BeautifulSoup) -> str:
    """Readable page text, one block per line, with boilerplate removed.

    Mutates *soup* (boilerplate tags are dropped), so run it after
    link and image extraction.
    """
    for tag in soup(_BOILERPLATE):
        tag.decompose()
    for comment in soup.find_all(string=lambda node: isinstance(node, Comment)):
        comment.extract()

    lines = (" ".join(line.split()) for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)
