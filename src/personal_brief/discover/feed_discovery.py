"""Best-effort RSS/Atom feed autodiscovery for a Discover-suggested domain.

Fetches the domain's homepage and looks for a standard
``<link rel="alternate" type="application/rss+xml|atom+xml">`` tag — the same
mechanism browsers and feed readers use. Never raises: a domain with no
discoverable feed still becomes a suggestion (see ``mining.py``), just
without a ready-to-follow URL.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin

import feedparser
import requests

DEFAULT_TIMEOUT_SECONDS = 15.0
_FEED_TYPES = {"application/rss+xml", "application/atom+xml"}


class _FeedLinkParser(HTMLParser):
    """Collects the first ``<link rel="alternate" type="...+xml">`` href found."""

    def __init__(self) -> None:
        super().__init__()
        self.feed_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.feed_href is not None or tag != "link":
            return
        attributes = dict(attrs)
        if attributes.get("rel") == "alternate" and attributes.get("type") in _FEED_TYPES:
            href = attributes.get("href")
            if href:
                self.feed_href = href


def discover_feed_url(
    domain: str, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> tuple[str, str] | None:
    """Try to find a feed URL and title for ``domain``.

    Returns ``(feed_url, feed_title)``, or ``None`` if the homepage can't be
    fetched or no feed link is found there.
    """
    homepage = f"https://{domain}"
    try:
        response = requests.get(homepage, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    parser = _FeedLinkParser()
    parser.feed(response.text)
    if parser.feed_href is None:
        return None

    feed_url = urljoin(homepage, parser.feed_href)
    title = _feed_title(feed_url, timeout) or domain
    return feed_url, title


def _feed_title(feed_url: str, timeout: float) -> str | None:
    # Fetched via requests (not feedparser's own urllib fetch) so the request
    # goes through the same HTTP layer as the rest of the codebase, and can be
    # mocked in tests the same way (see tests/test_feed_discovery.py).
    try:
        response = requests.get(feed_url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None
    parsed = feedparser.parse(response.content)
    title = parsed.get("feed", {}).get("title")
    return str(title) if title else None
