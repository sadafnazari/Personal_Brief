"""Normalized data types shared across the pipeline.

Every source, regardless of origin (RSS, Hacker News, Reddit, ...), converts its
raw payload into an :class:`Item`. Downstream stages (dedupe, summarize, deliver)
only ever see :class:`Item`, so adding a new source never ripples past this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Pillar(StrEnum):
    """Which of the three goals an item serves."""

    FOLLOW = "follow"  # people you deliberately track
    TRENDS = "trends"  # what is gaining traction right now
    DISCOVER = "discover"  # new voices worth following


@dataclass(frozen=True, slots=True)
class Item:
    """A single piece of content, normalized from any source."""

    pillar: Pillar
    source: str
    external_id: str
    title: str
    url: str
    published_at: datetime | None = None
    author: str | None = None
    body: str = ""
    score: int | None = None

    @property
    def dedupe_key(self) -> str:
        """Stable identity used to tell whether we have already seen this item."""
        return f"{self.source}:{self.external_id}"
