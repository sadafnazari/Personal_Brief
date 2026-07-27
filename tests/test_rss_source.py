from __future__ import annotations

from pathlib import Path

import pytest

from personal_brief.models import Pillar
from personal_brief.sources import SourceError
from personal_brief.sources.rss import RssSource

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


def test_fetch_parses_entries_into_items() -> None:
    source = RssSource(name="Sample Blog", url=str(FIXTURE))

    items = source.fetch()

    assert len(items) == 2
    first = items[0]
    assert first.pillar is Pillar.FOLLOW
    assert first.source == "Sample Blog"
    assert first.title == "Second Post"
    assert first.author == "Jane Doe"
    assert first.external_id == "https://example.com/posts/second"
    assert first.published_at is not None
    assert first.published_at.year == 2026


def test_fetch_respects_max_items() -> None:
    source = RssSource(name="Sample Blog", url=str(FIXTURE), max_items=1)

    items = source.fetch()

    assert len(items) == 1


def test_fetch_raises_source_error_for_unreachable_feed() -> None:
    source = RssSource(name="Broken", url="not-a-valid-url-at-all")

    with pytest.raises(SourceError):
        source.fetch()
