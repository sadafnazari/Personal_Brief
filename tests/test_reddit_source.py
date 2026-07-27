from __future__ import annotations

import requests
import responses

from personal_brief.models import Pillar
from personal_brief.sources import SourceError
from personal_brief.sources.reddit import RedditSource


def _reddit_response(posts: list[dict[str, object]]) -> dict[str, object]:
    return {"data": {"children": [{"data": post} for post in posts]}}


@responses.activate
def test_fetch_filters_by_min_upvotes() -> None:
    responses.add(
        responses.GET,
        "https://www.reddit.com/r/testsub/hot.json",
        json=_reddit_response(
            [
                {
                    "id": "abc",
                    "title": "Popular post",
                    "permalink": "/r/testsub/comments/abc/popular_post/",
                    "author": "alice",
                    "ups": 500,
                    "created_utc": 1735689600,
                    "selftext": "body text",
                },
                {
                    "id": "def",
                    "title": "Quiet post",
                    "permalink": "/r/testsub/comments/def/quiet_post/",
                    "author": "bob",
                    "ups": 10,
                    "created_utc": 1735689600,
                },
            ]
        ),
        status=200,
    )

    items = RedditSource(subreddit="testsub", min_upvotes=200).fetch()

    assert len(items) == 1
    item = items[0]
    assert item.title == "Popular post"
    assert item.pillar is Pillar.TRENDS
    assert item.source == "r/testsub"
    assert item.score == 500
    assert item.url == "https://www.reddit.com/r/testsub/comments/abc/popular_post/"
    assert item.published_at is not None


@responses.activate
def test_fetch_respects_max_items() -> None:
    posts = [
        {"id": str(i), "title": f"Post {i}", "ups": 300, "permalink": f"/r/testsub/{i}/"}
        for i in range(5)
    ]
    responses.add(
        responses.GET,
        "https://www.reddit.com/r/testsub/hot.json",
        json=_reddit_response(posts),
        status=200,
    )

    items = RedditSource(subreddit="testsub", min_upvotes=0, max_items=2).fetch()

    assert len(items) == 2


@responses.activate
def test_fetch_raises_source_error_on_connection_failure() -> None:
    responses.add(
        responses.GET,
        "https://www.reddit.com/r/testsub/hot.json",
        body=requests.exceptions.ConnectionError("refused"),
    )

    try:
        RedditSource(subreddit="testsub", min_upvotes=200).fetch()
        raise AssertionError("expected SourceError")
    except SourceError:
        pass


@responses.activate
def test_fetch_raises_source_error_on_malformed_response() -> None:
    responses.add(
        responses.GET,
        "https://www.reddit.com/r/testsub/hot.json",
        json={"unexpected": True},
    )

    try:
        RedditSource(subreddit="testsub", min_upvotes=200).fetch()
        raise AssertionError("expected SourceError")
    except SourceError:
        pass
