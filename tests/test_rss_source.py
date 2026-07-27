from __future__ import annotations

from pathlib import Path

import requests
import responses

from personal_brief.models import Pillar
from personal_brief.sources import SourceError
from personal_brief.sources.rss import RssSource

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"
FEED_URL = "https://example.com/feed.atom"


@responses.activate
def test_fetch_parses_entries_into_items() -> None:
    responses.add(responses.GET, FEED_URL, body=FIXTURE.read_bytes(), status=200)
    source = RssSource(name="Sample Blog", url=FEED_URL)

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


@responses.activate
def test_fetch_respects_max_items() -> None:
    responses.add(responses.GET, FEED_URL, body=FIXTURE.read_bytes(), status=200)
    source = RssSource(name="Sample Blog", url=FEED_URL, max_items=1)

    items = source.fetch()

    assert len(items) == 1


def test_fetch_raises_source_error_for_unreachable_feed() -> None:
    source = RssSource(name="Broken", url="not-a-valid-url-at-all")

    try:
        source.fetch()
        raise AssertionError("expected SourceError")
    except SourceError:
        pass


@responses.activate
def test_fetch_raises_source_error_on_http_error() -> None:
    responses.add(responses.GET, FEED_URL, status=404)
    source = RssSource(name="Sample Blog", url=FEED_URL)

    try:
        source.fetch()
        raise AssertionError("expected SourceError")
    except SourceError:
        pass


@responses.activate
def test_fetch_raises_source_error_on_connection_failure() -> None:
    responses.add(
        responses.GET,
        FEED_URL,
        body=requests.exceptions.ConnectionError("refused"),
    )
    source = RssSource(name="Sample Blog", url=FEED_URL)

    try:
        source.fetch()
        raise AssertionError("expected SourceError")
    except SourceError:
        pass


@responses.activate
def test_fetch_uses_configured_timeout() -> None:
    responses.add(responses.GET, FEED_URL, body=FIXTURE.read_bytes(), status=200)
    source = RssSource(name="Sample Blog", url=FEED_URL, timeout=5.0)

    source.fetch()

    assert responses.calls[0].request.req_kwargs.get("timeout") == 5.0  # type: ignore[attr-defined]
