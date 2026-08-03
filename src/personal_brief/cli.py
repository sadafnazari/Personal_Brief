"""Command-line entry point.

``personal-brief run`` fetches new items from every configured Follow and
Trends source, summarizes the unseen ones, writes a dated HTML digest to
``data/digests/``, and delivers it via any enabled channel (Telegram). If
Discover is enabled, it also applies any pending Telegram approve/reject
replies, mines Trends items for new domains to suggest, and folds pending
suggestions into the same digest.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from personal_brief import __version__
from personal_brief.config import Config, ConfigError, load_config
from personal_brief.deliver import (
    TELEGRAM_BOT_TOKEN_ENV_VAR,
    TELEGRAM_CHAT_ID_ENV_VAR,
    DeliveryError,
    create_deliverer,
)
from personal_brief.deliver.telegram import TelegramDeliverer
from personal_brief.digest import render_digest, render_telegram_messages, write_digest
from personal_brief.discover import mining
from personal_brief.discover.replies import process_replies
from personal_brief.env import load_dotenv
from personal_brief.models import Item, Pillar
from personal_brief.sources import Source, SourceError
from personal_brief.sources.hackernews import HackerNewsSource
from personal_brief.sources.rss import RssSource
from personal_brief.store import DiscoveredAuthor, Store, resolve_data_dir
from personal_brief.summarize import SummarizerError, create_summarizer

logger = logging.getLogger("personal_brief")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and dispatch to the chosen command. Returns an exit code."""
    load_dotenv()
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _run()

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="personal-brief",
        description="Follow the people and trends worth your attention.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Fetch new items and write today's digest.")
    return parser


def _run() -> int:
    try:
        config = load_config()
    except ConfigError as error:
        logger.error("Cannot start: %s", error)
        return 1

    data_dir = resolve_data_dir()
    with Store.open(data_dir) as store:
        return _build_digest(config, store, data_dir)


def _build_digest(config: Config, store: Store, data_dir: Path) -> int:
    _process_discover_replies(config, store)

    items = _fetch_all(config, store)
    new_items = store.filter_unseen(items)
    logger.info("Fetched %d item(s); %d are new.", len(items), len(new_items))

    discover_items = _mine_and_build_discover_items(config, store, items)

    if not new_items and not discover_items:
        logger.info("Nothing new today — no digest generated.")
        return 0

    try:
        summarizer = create_summarizer(config.summarizer)
        summary = summarizer.summarize(new_items)
    except SummarizerError as error:
        logger.error("Could not summarize: %s", error)
        return 1

    generated_at = datetime.now(UTC)
    digest_items = [*new_items, *discover_items]
    html = render_digest(digest_items, summary, generated_at)
    digest_path = write_digest(html, data_dir, generated_at)

    # Only genuinely new Follow/Trends items are dedupe-tracked. Discover
    # suggestions are stateful via discovered_authors — they keep reappearing
    # in every digest until approved or rejected.
    for item in new_items:
        store.mark_seen(item)

    logger.info("Digest written to %s", digest_path)
    _deliver(config, digest_items, summary, generated_at)
    return 0


def _process_discover_replies(config: Config, store: Store) -> None:
    """Best-effort: apply any Telegram approve/reject replies since last run."""
    if not (config.discover.enabled and config.delivery.telegram):
        return

    bot_token = os.environ.get(TELEGRAM_BOT_TOKEN_ENV_VAR)
    chat_id = os.environ.get(TELEGRAM_CHAT_ID_ENV_VAR)
    if not bot_token or not chat_id:
        return

    deliverer = TelegramDeliverer(bot_token=bot_token, chat_id=chat_id)
    try:
        decided = process_replies(deliverer, store, chat_id)
        if decided:
            logger.info("Applied %d Discover decision(s) from Telegram.", decided)
    except DeliveryError as error:
        logger.warning("Could not poll Telegram for Discover replies: %s", error)


def _mine_and_build_discover_items(config: Config, store: Store, items: list[Item]) -> list[Item]:
    """Mine Trends items for new suggestions, then render every pending one."""
    if not config.discover.enabled:
        return []

    trends_items = [item for item in items if item.pillar is Pillar.TRENDS]
    known_domains = mining.followed_domains(config, store)
    mining.mine(trends_items, known_domains, store, config.discover.min_sightings)

    return [_suggestion_to_item(author) for author in store.get_pending_suggestions()]


def _suggestion_to_item(author: DiscoveredAuthor) -> Item:
    return Item(
        pillar=Pillar.DISCOVER,
        source="Discover",
        external_id=author.name,
        title=author.name,
        url=author.feed_url or f"https://{author.name}",
        author=f"reply 'approve {author.name}' to follow · {author.reason}",
    )


def _deliver(config: Config, items: list[Item], summary: str, generated_at: datetime) -> None:
    """Best-effort delivery — a failure here is logged, never fatal.

    By this point the local HTML digest already exists on disk, so a broken
    Telegram bot means "you'll have to open the file yourself today," not
    "the run failed."
    """
    try:
        deliverer = create_deliverer(config.delivery)
    except DeliveryError as error:
        logger.error("Delivery not configured correctly: %s", error)
        return

    if deliverer is None:
        return

    try:
        messages = render_telegram_messages(items, summary, generated_at)
        for message in messages:
            deliverer.deliver(message, parse_mode="HTML")
        logger.info("Digest delivered via Telegram (%d message(s)).", len(messages))
    except DeliveryError as error:
        logger.error("Could not deliver digest via Telegram: %s", error)


def _fetch_all(config: Config, store: Store) -> list[Item]:
    items: list[Item] = []
    for name, source in _build_sources(config, store):
        try:
            items.extend(source.fetch())
        except SourceError as error:
            logger.warning("Skipping '%s': %s", name, error)
    return items


def _build_sources(config: Config, store: Store) -> list[tuple[str, Source]]:
    sources: list[tuple[str, Source]] = [
        (follow.name, RssSource(name=follow.name, url=follow.rss)) for follow in config.follow
    ]

    known_rss_urls = {follow.rss for follow in config.follow}
    for author in store.get_approved_authors():
        if author.feed_url and author.feed_url not in known_rss_urls:
            sources.append((author.name, RssSource(name=author.name, url=author.feed_url)))
            known_rss_urls.add(author.feed_url)

    if config.trends.hackernews is not None:
        sources.append(
            ("Hacker News", HackerNewsSource(min_points=config.trends.hackernews.min_points))
        )

    return sources


def _configure_logging() -> None:
    level_name = os.environ.get("PERSONAL_BRIEF_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
