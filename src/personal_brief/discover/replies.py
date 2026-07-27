"""Applies Telegram commands to the store: mining decisions and manual follows.

``personal-brief run`` stays a single scheduled command — no persistent
listener or webhook. Each run does one short, non-blocking ``getUpdates``
poll to pick up anything sent since the last run's offset, applies whatever
it recognizes, and sends back one confirmation message so a reply is never
silent.

Two command shapes:

* ``approve <domain>`` / ``reject <domain>`` — decide a mining suggestion
  from ``mining.py`` (see ``discovered_authors``).
* ``follow <name> <rss-url>`` — add any feed directly, validated against a
  real fetch before being stored, no suggest/approve step needed since the
  user already made the decision.
"""

from __future__ import annotations

import logging
import re

from personal_brief.deliver import DeliveryError
from personal_brief.deliver.telegram import TelegramDeliverer
from personal_brief.sources import SourceError
from personal_brief.sources.rss import RssSource
from personal_brief.store import STATUS_APPROVED, STATUS_REJECTED, Store

logger = logging.getLogger("personal_brief")

_DECIDE_PATTERN = re.compile(r"^(approve|reject)\s+(\S+)$", re.IGNORECASE)
_FOLLOW_PATTERN = re.compile(r"^follow\s+(.+?)\s+(https?://\S+)$", re.IGNORECASE)


def process_replies(deliverer: TelegramDeliverer, store: Store, chat_id: str) -> int:
    """Poll for new Telegram messages and apply any recognized commands.

    Sends one confirmation message back (via ``deliverer``) summarizing what
    was applied, if anything was. Returns the number of commands processed.
    Messages from a different chat, or that match neither command shape, are
    ignored.
    """
    updates = deliverer.get_updates(offset=store.get_update_offset())
    confirmations: list[str] = []
    highest_update_id: int | None = None

    for update in updates:
        highest_update_id = update["update_id"]
        message = update.get("message")
        if not message or str(message.get("chat", {}).get("id")) != chat_id:
            continue

        text = str(message.get("text", "")).strip()
        confirmation = _apply_decide_command(store, text) or _apply_follow_command(store, text)
        if confirmation:
            confirmations.append(confirmation)

    if highest_update_id is not None:
        store.set_update_offset(highest_update_id + 1)

    if confirmations:
        try:
            deliverer.deliver("\n".join(confirmations))
        except DeliveryError as error:
            logger.warning("Could not send Discover confirmation via Telegram: %s", error)

    return len(confirmations)


def _apply_decide_command(store: Store, text: str) -> str | None:
    match = _DECIDE_PATTERN.match(text)
    if not match:
        return None

    action, domain = match.group(1).lower(), match.group(2)
    status = STATUS_APPROVED if action == "approve" else STATUS_REJECTED
    store.update_suggestion_status(domain, status)
    logger.info("Discover: '%s' %s via Telegram reply.", domain, status)
    return f"✓ {action.capitalize()}d {domain}"


def _apply_follow_command(store: Store, text: str) -> str | None:
    match = _FOLLOW_PATTERN.match(text)
    if not match:
        return None

    name, feed_url = match.group(1).strip(), match.group(2)
    try:
        RssSource(name=name, url=feed_url).fetch()
    except SourceError as error:
        logger.warning("Discover: could not add '%s' (%s): %s", name, feed_url, error)
        return f'✗ Could not add "{name}": {error}'

    store.add_approved_author(name, feed_url, reason="added manually via Telegram")
    logger.info("Discover: '%s' (%s) added via Telegram follow command.", name, feed_url)
    return f'✓ Added "{name}" ({feed_url}) to Follow'
