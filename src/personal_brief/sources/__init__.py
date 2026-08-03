"""Source plugins.

Every source (RSS, Hacker News, ... more later) implements the
:class:`Source` protocol and returns a list of normalized
:class:`~personal_brief.models.Item`. Nothing downstream cares which source an
item came from, so adding a new one is a single new file here plus a factory
entry — the rest of the pipeline never changes.
"""

from __future__ import annotations

from typing import Protocol

from personal_brief.models import Item


class Source(Protocol):
    """Anything that can produce a list of items for the pipeline."""

    def fetch(self) -> list[Item]:
        """Fetch and return the current items from this source.

        Implementations should raise :class:`SourceError` on failure rather
        than letting a source-specific exception escape — the caller treats
        one failing source as a warning, not a fatal error for the whole run.
        """
        ...


class SourceError(Exception):
    """Raised when a source fails to fetch or parse its content."""
