from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import responses

from personal_brief.deliver.telegram import DEFAULT_BASE_URL, TelegramDeliverer
from personal_brief.discover.replies import process_replies
from personal_brief.sources import SourceError
from personal_brief.store import Store


def _updates_response(*updates: dict[str, object]) -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/bottest-token/getUpdates",
        json={"ok": True, "result": list(updates)},
        status=200,
    )


def _mock_send_message() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/bottest-token/sendMessage",
        json={"ok": True},
        status=200,
    )


def _json_body(body: bytes | str | None) -> Any:
    assert body is not None
    return json.loads(body)


def _message_update(update_id: int, chat_id: str, text: str) -> dict[str, object]:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": int(chat_id)}, "text": text},
    }


@responses.activate
def test_approve_reply_marks_suggestion_approved(tmp_path: Path) -> None:
    _updates_response(_message_update(1, "12345", "approve example.com"))
    _mock_send_message()
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store:
        store.create_suggestion("example.com", feed_url="https://example.com/feed", reason="x")

        decided = process_replies(deliverer, store, chat_id="12345")

        assert decided == 1
        assert store.get_pending_suggestions() == []
        assert len(store.get_approved_authors()) == 1


@responses.activate
def test_reject_reply_marks_suggestion_rejected(tmp_path: Path) -> None:
    _updates_response(_message_update(1, "12345", "reject example.com"))
    _mock_send_message()
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store:
        store.create_suggestion("example.com", feed_url="https://example.com/feed", reason="x")

        process_replies(deliverer, store, chat_id="12345")

        assert store.get_pending_suggestions() == []
        assert store.get_approved_authors() == []


@responses.activate
def test_reply_from_other_chat_is_ignored(tmp_path: Path) -> None:
    _updates_response(_message_update(1, "99999", "approve example.com"))
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store:
        store.create_suggestion("example.com", feed_url="https://example.com/feed", reason="x")

        decided = process_replies(deliverer, store, chat_id="12345")

        assert decided == 0
        assert len(store.get_pending_suggestions()) == 1


@responses.activate
def test_unrecognized_text_is_ignored(tmp_path: Path) -> None:
    _updates_response(_message_update(1, "12345", "hello there"))
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store:
        decided = process_replies(deliverer, store, chat_id="12345")

        assert decided == 0


@responses.activate
def test_offset_persists_and_is_sent_on_next_poll(tmp_path: Path) -> None:
    _updates_response(_message_update(5, "12345", "approve example.com"))
    _mock_send_message()
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store:
        store.create_suggestion("example.com", feed_url="https://example.com/feed", reason="x")
        process_replies(deliverer, store, chat_id="12345")

        assert store.get_update_offset() == 6


@responses.activate
def test_follow_command_adds_a_validated_feed(tmp_path: Path) -> None:
    _updates_response(
        _message_update(1, "12345", "follow Kyle Kingsbury https://aphyr.com/posts.atom")
    )
    _mock_send_message()
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store, patch("personal_brief.discover.replies.RssSource") as rss:
        rss.return_value.fetch.return_value = []

        decided = process_replies(deliverer, store, chat_id="12345")

        assert decided == 1
        rss.assert_called_once_with(name="Kyle Kingsbury", url="https://aphyr.com/posts.atom")
        approved = store.get_approved_authors()
        assert len(approved) == 1
        assert approved[0].name == "Kyle Kingsbury"
        assert approved[0].feed_url == "https://aphyr.com/posts.atom"


@responses.activate
def test_follow_command_with_unfetchable_feed_is_not_stored(tmp_path: Path) -> None:
    _updates_response(_message_update(1, "12345", "follow Bad Blog https://bad.example/feed"))
    _mock_send_message()
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store, patch("personal_brief.discover.replies.RssSource") as rss:
        rss.return_value.fetch.side_effect = SourceError("could not fetch feed")

        decided = process_replies(deliverer, store, chat_id="12345")

        assert decided == 1
        assert store.get_approved_authors() == []
        sent_body = _json_body(responses.calls[-1].request.body)
        assert "Could not add" in sent_body["text"]


@responses.activate
def test_confirmation_message_is_sent_once_for_multiple_commands(tmp_path: Path) -> None:
    _updates_response(
        _message_update(1, "12345", "approve example.com"),
        _message_update(2, "12345", "follow Kyle Kingsbury https://aphyr.com/posts.atom"),
    )
    _mock_send_message()
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    with Store.open(tmp_path) as store, patch("personal_brief.discover.replies.RssSource") as rss:
        rss.return_value.fetch.return_value = []
        store.create_suggestion("example.com", feed_url="https://example.com/feed", reason="x")

        decided = process_replies(deliverer, store, chat_id="12345")

        assert decided == 2
        send_message_calls = [
            call
            for call in responses.calls
            if call.request.url and "sendMessage" in call.request.url
        ]
        assert len(send_message_calls) == 1
        sent_body = _json_body(send_message_calls[0].request.body)
        assert "example.com" in sent_body["text"]
        assert "Kyle Kingsbury" in sent_body["text"]
