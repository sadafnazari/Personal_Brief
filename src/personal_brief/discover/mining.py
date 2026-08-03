"""Mines domains out of Trends items to find new voices worth following.

No new network calls beyond what Trends sources already fetch: every run,
Hacker News and Reddit items are already being pulled for the Trends pillar.
This module just counts which unfollowed external domains keep showing up
in them, and promotes a domain to a suggestion once it crosses
``min_sightings`` — no LLM guessing, no hallucinated URLs.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from personal_brief.config import Config
from personal_brief.discover.feed_discovery import discover_feed_url
from personal_brief.models import Item
from personal_brief.store import STATUS_REJECTED, Store

# Aggregator self-domains and major shared hosting/platform domains are never
# a useful "who to follow" suggestion — they're not an author/voice, just
# infrastructure that happens to host one.
_PLATFORM_DOMAINS = {
    "news.ycombinator.com",
    "reddit.com",
    "www.reddit.com",
    "redd.it",
    "github.com",
    "gist.github.com",
    "gitlab.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
    "npmjs.com",
    "pypi.org",
    "crates.io",
    "arxiv.org",
    "en.wikipedia.org",
    "wikipedia.org",
    "stackoverflow.com",
    "developer.mozilla.org",
    "linkedin.com",
}


def extract_domain(item: Item) -> str | None:
    """Return the item's URL host, or ``None`` for aggregator/platform domains."""
    netloc = urlparse(item.url).netloc
    if not netloc or netloc in _PLATFORM_DOMAINS:
        return None
    return netloc


def followed_domains(config: Config, store: Store) -> set[str]:
    """Domains already covered by config-based or Discover-approved follows."""
    domains = {urlparse(follow.rss).netloc for follow in config.follow}
    domains.update(
        urlparse(author.feed_url).netloc
        for author in store.get_approved_authors()
        if author.feed_url
    )
    return domains


def prune_platform_suggestions(store: Store) -> None:
    """Reject pending suggestions for domains ``_PLATFORM_DOMAINS`` later grew to cover.

    ``_PLATFORM_DOMAINS`` has been extended over time; a suggestion created
    before a domain was added (e.g. "github.com", suggested before it was
    blocklisted) would otherwise sit as 'suggested' — and keep showing up in
    every digest — forever. Run this once per pipeline run so both local and
    production stores self-heal without a manual data fix.
    """
    for author in store.get_pending_suggestions():
        if author.name in _PLATFORM_DOMAINS:
            store.update_suggestion_status(author.name, STATUS_REJECTED)


def mine(
    trends_items: Iterable[Item],
    known_domains: set[str],
    store: Store,
    min_sightings: int,
) -> None:
    """Record sightings for unfollowed domains and promote ones past the threshold."""
    for item in trends_items:
        domain = extract_domain(item)
        if domain is None or domain in known_domains or store.is_known_domain(domain):
            continue

        count = store.record_domain_sighting(domain)
        if count < min_sightings:
            continue

        discovered = discover_feed_url(domain)
        if discovered is None:
            store.create_suggestion(
                domain, feed_url=None, reason=f"seen {count}x in Trends — no feed auto-detected"
            )
        else:
            feed_url, feed_title = discovered
            store.create_suggestion(
                domain, feed_url=feed_url, reason=f"'{feed_title}' — seen {count}x in Trends"
            )
