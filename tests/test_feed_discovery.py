from __future__ import annotations

import responses

from personal_brief.discover.feed_discovery import discover_feed_url

_ATOM_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Example Blog</title></feed>
"""


@responses.activate
def test_discover_feed_url_finds_absolute_link() -> None:
    responses.add(
        responses.GET,
        "https://example.com",
        body='<html><head><link rel="alternate" type="application/atom+xml" '
        'href="https://example.com/feed.atom"></head></html>',
        status=200,
    )
    responses.add(responses.GET, "https://example.com/feed.atom", body=_ATOM_FEED, status=200)

    result = discover_feed_url("example.com")

    assert result == ("https://example.com/feed.atom", "Example Blog")


@responses.activate
def test_discover_feed_url_resolves_relative_link() -> None:
    responses.add(
        responses.GET,
        "https://example.com",
        body='<html><head><link rel="alternate" type="application/rss+xml" '
        'href="/rss.xml"></head></html>',
        status=200,
    )
    responses.add(responses.GET, "https://example.com/rss.xml", body=_ATOM_FEED, status=200)

    result = discover_feed_url("example.com")

    assert result == ("https://example.com/rss.xml", "Example Blog")


@responses.activate
def test_discover_feed_url_returns_none_when_no_feed_link() -> None:
    responses.add(
        responses.GET, "https://example.com", body="<html><head></head></html>", status=200
    )

    assert discover_feed_url("example.com") is None


@responses.activate
def test_discover_feed_url_returns_none_when_homepage_unreachable() -> None:
    responses.add(responses.GET, "https://example.com", status=500)

    assert discover_feed_url("example.com") is None
