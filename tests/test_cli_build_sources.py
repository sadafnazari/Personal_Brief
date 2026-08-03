from __future__ import annotations

from pathlib import Path

from personal_brief.cli import _build_sources
from personal_brief.config import (
    Config,
    DeliveryConfig,
    DiscoverConfig,
    FollowSource,
    HackerNewsConfig,
    SummarizerConfig,
    TrendsConfig,
)
from personal_brief.sources.hackernews import HackerNewsSource
from personal_brief.sources.rss import RssSource
from personal_brief.store import Store


def _config(**trends_kwargs: object) -> Config:
    return Config(
        interests=(),
        follow=(FollowSource(name="Martin Fowler", rss="https://martinfowler.com/feed.atom"),),
        trends=TrendsConfig(**trends_kwargs),  # type: ignore[arg-type]
        summarizer=SummarizerConfig(provider="ollama", model=None),
        delivery=DeliveryConfig(telegram=False),
        discover=DiscoverConfig(),
    )


def test_build_sources_includes_follow_only_by_default(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        sources = _build_sources(_config(), store)

    assert [name for name, _ in sources] == ["Martin Fowler"]
    assert isinstance(sources[0][1], RssSource)


def test_build_sources_includes_hackernews_when_configured(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        sources = _build_sources(_config(hackernews=HackerNewsConfig(min_points=100)), store)

    names = [name for name, _ in sources]
    assert "Hacker News" in names
    hn_source = dict(sources)["Hacker News"]
    assert isinstance(hn_source, HackerNewsSource)
    assert hn_source.min_points == 100


def test_build_sources_includes_approved_discover_authors(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion("aphyr.com", feed_url="https://aphyr.com/posts.atom", reason="test")
        store.update_suggestion_status("aphyr.com", "approved")

        sources = _build_sources(_config(), store)

    names = [name for name, _ in sources]
    assert "aphyr.com" in names
    aphyr_source = dict(sources)["aphyr.com"]
    assert isinstance(aphyr_source, RssSource)
    assert aphyr_source.url == "https://aphyr.com/posts.atom"


def test_build_sources_does_not_duplicate_an_already_followed_feed(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion(
            "martinfowler.com", feed_url="https://martinfowler.com/feed.atom", reason="test"
        )
        store.update_suggestion_status("martinfowler.com", "approved")

        sources = _build_sources(_config(), store)

    names = [name for name, _ in sources]
    assert names.count("Martin Fowler") == 1
    assert "martinfowler.com" not in names


def test_build_sources_does_not_duplicate_two_approved_authors_sharing_a_feed(
    tmp_path: Path,
) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion("aphyr.com", feed_url="https://aphyr.com/posts.atom", reason="x")
        store.update_suggestion_status("aphyr.com", "approved")
        store.add_approved_author("Kyle Kingsbury", "https://aphyr.com/posts.atom", reason="manual")

        sources = _build_sources(_config(), store)

    feed_urls = [source.url for _, source in sources if isinstance(source, RssSource)]
    assert feed_urls.count("https://aphyr.com/posts.atom") == 1
