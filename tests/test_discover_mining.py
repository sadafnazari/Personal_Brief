from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from personal_brief.config import (
    Config,
    DeliveryConfig,
    DiscoverConfig,
    FollowSource,
    SummarizerConfig,
    TrendsConfig,
)
from personal_brief.discover import mining
from personal_brief.models import Item, Pillar
from personal_brief.store import Store


def _trends_item(url: str, external_id: str) -> Item:
    return Item(
        pillar=Pillar.TRENDS,
        source="Hacker News",
        external_id=external_id,
        title="Some post",
        url=url,
    )


def _config() -> Config:
    return Config(
        interests=(),
        follow=(FollowSource(name="Martin Fowler", rss="https://martinfowler.com/feed.atom"),),
        trends=TrendsConfig(),
        summarizer=SummarizerConfig(provider="ollama", model=None),
        delivery=DeliveryConfig(telegram=False),
        discover=DiscoverConfig(enabled=True, min_sightings=2),
    )


def test_extract_domain_returns_netloc() -> None:
    item = _trends_item("https://aphyr.com/posts/1", "1")
    assert mining.extract_domain(item) == "aphyr.com"


def test_extract_domain_excludes_aggregator_self_posts() -> None:
    hn_self_post = _trends_item("https://news.ycombinator.com/item?id=1", "1")
    reddit_self_post = _trends_item("https://www.reddit.com/r/programming/comments/1/x/", "2")
    assert mining.extract_domain(hn_self_post) is None
    assert mining.extract_domain(reddit_self_post) is None


def test_followed_domains_includes_config_and_approved(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion("aphyr.com", feed_url="https://aphyr.com/posts.atom", reason="x")
        store.update_suggestion_status("aphyr.com", "approved")

        domains = mining.followed_domains(_config(), store)

    assert domains == {"martinfowler.com", "aphyr.com"}


def test_mine_does_not_suggest_below_threshold(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        items = [_trends_item("https://newblog.com/a", "1")]
        mining.mine(items, known_domains=set(), store=store, min_sightings=2)

        assert store.get_pending_suggestions() == []


def test_mine_suggests_once_threshold_reached(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        items = [
            _trends_item("https://newblog.com/a", "1"),
            _trends_item("https://newblog.com/b", "2"),
        ]
        with patch("personal_brief.discover.mining.discover_feed_url", return_value=None):
            mining.mine(items, known_domains=set(), store=store, min_sightings=2)

        pending = store.get_pending_suggestions()
        assert len(pending) == 1
        assert pending[0].name == "newblog.com"


def test_mine_skips_already_followed_domains(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        items = [
            _trends_item("https://martinfowler.com/a", "1"),
            _trends_item("https://martinfowler.com/b", "2"),
        ]
        mining.mine(items, known_domains={"martinfowler.com"}, store=store, min_sightings=2)

        assert store.get_pending_suggestions() == []


def test_mine_skips_domains_already_decided(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion("newblog.com", feed_url=None, reason="already suggested")
        items = [
            _trends_item("https://newblog.com/a", "1"),
            _trends_item("https://newblog.com/b", "2"),
        ]

        mining.mine(items, known_domains=set(), store=store, min_sightings=2)

        # Still exactly the one original suggestion, sightings weren't recorded again.
        assert len(store.get_pending_suggestions()) == 1
