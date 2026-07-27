"""Deliverer plugins.

A deliverer sends the rendered digest somewhere the user will actually see
it (Telegram today; email or Slack could follow the same shape later). It is
pluggable so the pipeline never needs to know which channel is active.

A delivery failure is deliberately **not** fatal to the run: by the time
delivery is attempted, the local HTML digest already exists on disk as a
fallback, so we log the failure and move on rather than treating a dead
Telegram bot as a reason to lose the summary work already done.
"""

from __future__ import annotations

import os
from typing import Protocol

from personal_brief.config import DeliveryConfig

TELEGRAM_BOT_TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV_VAR = "TELEGRAM_CHAT_ID"


class Deliverer(Protocol):
    """Anything that can send the rendered digest text somewhere."""

    def deliver(self, text: str, parse_mode: str | None = None) -> None:
        """Send ``text`` to this channel.

        ``parse_mode`` is channel-specific formatting hint (e.g. Telegram's
        ``"HTML"``); implementations that don't support formatting can ignore
        it — it defaults to ``None`` (plain text).

        Raises:
            DeliveryError: if delivery fails.
        """
        ...


class DeliveryError(Exception):
    """Raised when a deliverer is misconfigured or fails to send."""


def create_deliverer(config: DeliveryConfig) -> Deliverer | None:
    """Build the deliverer implied by ``config``, or ``None`` if none is enabled.

    Raises:
        DeliveryError: if a channel is enabled but missing required secrets.
    """
    if not config.telegram:
        return None

    bot_token = os.environ.get(TELEGRAM_BOT_TOKEN_ENV_VAR)
    chat_id = os.environ.get(TELEGRAM_CHAT_ID_ENV_VAR)
    if not bot_token or not chat_id:
        raise DeliveryError(
            "delivery.telegram is enabled but "
            f"{TELEGRAM_BOT_TOKEN_ENV_VAR}/{TELEGRAM_CHAT_ID_ENV_VAR} are not set. "
            "Copy .env.example to .env and fill them in."
        )

    from personal_brief.deliver.telegram import TelegramDeliverer

    return TelegramDeliverer(bot_token=bot_token, chat_id=chat_id)
