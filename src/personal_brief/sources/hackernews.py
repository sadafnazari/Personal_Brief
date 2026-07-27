"""Hacker News source — powers the Trends pillar.

Uses the free Algolia HN Search API (no auth required) rather than the
official Firebase API, since it returns full story data (title, points,
author, url) in a single request instead of one request per story ID.
"""

from __future__ import annotations

from datetime import datetime

import requests

from personal_brief.models import Item, Pillar
from personal_brief.sources import SourceError

DEFAULT_BASE_URL = "https://hn.algolia.com/api/v1"
DEFAULT_MAX_ITEMS = 10
DEFAULT_TIMEOUT_SECONDS = 15.0


class HackerNewsSource:
    """Fetches the current Hacker News front page, filtered by a minimum score."""

    def __init__(
        self,
        min_points: int,
        max_items: int = DEFAULT_MAX_ITEMS,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.min_points = min_points
        self.max_items = max_items
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        """Fetch the front page and return items at or above ``min_points``.

        Raises:
            SourceError: if the API cannot be reached or returns an unexpected shape.
        """
        try:
            response = requests.get(
                f"{self.base_url}/search", params={"tags": "front_page"}, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise SourceError(f"Could not fetch Hacker News front page: {error}") from error

        try:
            hits = response.json()["hits"]
        except (ValueError, KeyError) as error:
            raise SourceError(f"Unexpected response from Hacker News: {error}") from error

        filtered = [hit for hit in hits if hit.get("points", 0) >= self.min_points]
        filtered.sort(key=lambda hit: hit.get("points", 0), reverse=True)
        return [self._to_item(hit) for hit in filtered[: self.max_items]]

    @staticmethod
    def _to_item(hit: dict[str, object]) -> Item:
        object_id = str(hit.get("objectID"))
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        points = hit.get("points")
        return Item(
            pillar=Pillar.TRENDS,
            source="Hacker News",
            external_id=object_id,
            title=str(hit.get("title") or "(untitled)"),
            url=str(url),
            published_at=_parse_hn_datetime(hit.get("created_at")),
            author=str(hit["author"]) if hit.get("author") else None,
            score=int(points) if isinstance(points, int) else None,
        )


def _parse_hn_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
