"""Telegram delivery via the Bot API.

Setup: message @BotFather to create a bot and get a token, then message your
new bot once and read https://api.telegram.org/bot<token>/getUpdates to find
your chat id. Put both in ``.env`` (see ``.env.example``).
"""

from __future__ import annotations

from typing import Any

import requests

from personal_brief.deliver import DeliveryError

DEFAULT_BASE_URL = "https://api.telegram.org"
DEFAULT_TIMEOUT_SECONDS = 15.0

# Telegram's hard limit is 4096 characters per message; stay comfortably under it.
MAX_MESSAGE_LENGTH = 4000


class TelegramDeliverer:
    """Sends text to a single Telegram chat via a bot, chunked to fit message limits."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def deliver(self, text: str, parse_mode: str | None = None) -> None:
        """Send ``text`` to the configured chat, splitting it if it's too long.

        Raises:
            DeliveryError: if any chunk fails to send.
        """
        for chunk in _chunk_message(text):
            self._send(chunk, parse_mode)

    def _send(self, text: str, parse_mode: str | None = None) -> None:
        url = f"{self.base_url}/bot{self.bot_token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise DeliveryError(f"Telegram delivery failed: {self._redact(error)}") from error

    def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        """Fetch new updates (e.g. replies) since ``offset``, a short non-blocking poll.

        Raises:
            DeliveryError: if the request fails.
        """
        url = f"{self.base_url}/bot{self.bot_token}/getUpdates"
        params: dict[str, Any] = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except requests.exceptions.RequestException as error:
            raise DeliveryError(
                f"Could not poll Telegram for updates: {self._redact(error)}"
            ) from error
        result: list[dict[str, Any]] = payload.get("result", [])
        return result

    def _redact(self, error: Exception) -> str:
        """Strip the bot token out of an exception's message before it's logged.

        ``requests`` includes the full request URL in its exception text, and
        Telegram's API puts the bot token *in* the URL — so an unredacted
        error message leaks the token into logs (local files, GitHub Actions
        run output, anywhere the log ends up).
        """
        return str(error).replace(self.bot_token, "***")


def _chunk_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split ``text`` into chunks at line boundaries, each at most ``max_length`` chars."""
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for line in text.split("\n"):
        line_length = len(line) + 1  # +1 for the newline that joins it back
        if current and current_length + line_length > max_length:
            chunks.append("\n".join(current))
            current = []
            current_length = 0
        current.append(line)
        current_length += line_length
    if current:
        chunks.append("\n".join(current))
    return chunks
