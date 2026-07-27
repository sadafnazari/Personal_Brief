from __future__ import annotations

import pytest

from personal_brief.config import DeliveryConfig
from personal_brief.deliver import DeliveryError, create_deliverer
from personal_brief.deliver.telegram import TelegramDeliverer


def test_create_deliverer_returns_none_when_disabled() -> None:
    assert create_deliverer(DeliveryConfig(telegram=False)) is None


def test_create_deliverer_raises_when_enabled_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(DeliveryError, match="TELEGRAM_BOT_TOKEN"):
        create_deliverer(DeliveryConfig(telegram=True))


def test_create_deliverer_returns_telegram_deliverer_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    deliverer = create_deliverer(DeliveryConfig(telegram=True))

    assert isinstance(deliverer, TelegramDeliverer)
    assert deliverer.bot_token == "test-token"
    assert deliverer.chat_id == "12345"
