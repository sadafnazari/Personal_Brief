from __future__ import annotations

import requests
import responses

from personal_brief.models import Pillar
from personal_brief.sources import SourceError
from personal_brief.sources.hackernews import DEFAULT_BASE_URL, HackerNewsSource

_HITS = [
    {
        "objectID": "1",
        "title": "Big story",
        "url": "https://a.example.com",
        "points": 300,
        "author": "alice",
        "created_at": "2026-01-02T10:00:00.000Z",
    },
    {
        "objectID": "2",
        "title": "Medium story",
        "url": "https://b.example.com",
        "points": 180,
        "author": "bob",
        "created_at": "2026-01-02T09:00:00.000Z",
    },
    {
        "objectID": "3",
        "title": "Small story",
        "points": 50,
        "author": "carol",
        "created_at": "2026-01-02T08:00:00.000Z",
    },
]


@responses.activate
def test_fetch_filters_by_min_points_and_sorts_descending() -> None:
    responses.add(responses.GET, f"{DEFAULT_BASE_URL}/search", json={"hits": _HITS}, status=200)

    items = HackerNewsSource(min_points=150).fetch()

    assert [item.title for item in items] == ["Big story", "Medium story"]
    assert items[0].score == 300
    assert items[0].pillar is Pillar.TRENDS
    assert items[0].source == "Hacker News"
    assert items[0].published_at is not None


@responses.activate
def test_fetch_falls_back_to_hn_link_when_no_url() -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/search",
        json={"hits": [{"objectID": "42", "title": "Ask HN", "points": 200}]},
        status=200,
    )

    items = HackerNewsSource(min_points=150).fetch()

    assert items[0].url == "https://news.ycombinator.com/item?id=42"


@responses.activate
def test_fetch_respects_max_items() -> None:
    responses.add(responses.GET, f"{DEFAULT_BASE_URL}/search", json={"hits": _HITS}, status=200)

    items = HackerNewsSource(min_points=0, max_items=1).fetch()

    assert len(items) == 1


@responses.activate
def test_fetch_raises_source_error_on_connection_failure() -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/search",
        body=requests.exceptions.ConnectionError("refused"),
    )

    try:
        HackerNewsSource(min_points=150).fetch()
        raise AssertionError("expected SourceError")
    except SourceError:
        pass


@responses.activate
def test_fetch_raises_source_error_on_malformed_response() -> None:
    responses.add(responses.GET, f"{DEFAULT_BASE_URL}/search", json={"unexpected": True})

    try:
        HackerNewsSource(min_points=150).fetch()
        raise AssertionError("expected SourceError")
    except SourceError:
        pass
