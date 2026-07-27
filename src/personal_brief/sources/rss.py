"""RSS/Atom source — powers the Follow pillar (Martin Fowler, etc.)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from time import struct_time

import feedparser
import requests

from personal_brief.models import Item, Pillar
from personal_brief.sources import SourceError

DEFAULT_MAX_ITEMS = 5
DEFAULT_TIMEOUT_SECONDS = 15.0


class RssSource:
    """Fetches the most recent entries from a single RSS/Atom feed."""

    def __init__(
        self,
        name: str,
        url: str,
        max_items: int = DEFAULT_MAX_ITEMS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.name = name
        self.url = url
        self.max_items = max_items
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        """Fetch and parse the feed, returning up to ``max_items`` normalized items.

        Raises:
            SourceError: if the feed cannot be fetched or contains no usable entries.
        """
        # Fetch via `requests` ourselves (bounded by `timeout`) rather than letting
        # feedparser do its own networking — feedparser's built-in fetch has no
        # timeout and can hang indefinitely against a slow or unresponsive feed.
        try:
            response = requests.get(self.url, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise SourceError(
                f"Could not fetch feed '{self.name}' ({self.url}): {error}"
            ) from error

        parsed = feedparser.parse(response.content)

        # feedparser never raises on parse failure — it sets `bozo` and stashes
        # the exception instead. Surface that as our own error type.
        if parsed.get("bozo") and not parsed.get("entries"):
            reason = parsed.get("bozo_exception", "unknown error")
            raise SourceError(f"Could not parse feed '{self.name}' ({self.url}): {reason}")

        return [self._to_item(entry) for entry in parsed.entries[: self.max_items]]

    def _to_item(self, entry: feedparser.FeedParserDict) -> Item:
        title = str(entry.get("title", "(untitled)"))
        url = str(entry.get("link", self.url))
        return Item(
            pillar=Pillar.FOLLOW,
            source=self.name,
            external_id=self._external_id(entry, url, title),
            title=title,
            url=url,
            published_at=_parse_published(entry.get("published_parsed")),
            author=str(entry.get("author")) if entry.get("author") else self.name,
            body=str(entry.get("summary", "")),
        )

    @staticmethod
    def _external_id(entry: feedparser.FeedParserDict, url: str, title: str) -> str:
        entry_id = entry.get("id")
        if entry_id:
            return str(entry_id)
        if url:
            return url
        # Last resort: a stable hash so the same (untitled, linkless) entry
        # is not treated as new on every run.
        return hashlib.sha256(title.encode("utf-8")).hexdigest()


def _parse_published(published_parsed: struct_time | None) -> datetime | None:
    if published_parsed is None:
        return None
    return datetime(*published_parsed[:6], tzinfo=UTC)
