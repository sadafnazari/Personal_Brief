from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import requests
import responses

from personal_brief.deliver import DeliveryError
from personal_brief.deliver.telegram import DEFAULT_BASE_URL, TelegramDeliverer, _chunk_message


@responses.activate
def test_deliver_sends_a_single_message_for_short_text() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/bottest-token/sendMessage",
        json={"ok": True},
        status=200,
    )
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    deliverer.deliver("Short digest text.")

    assert len(responses.calls) == 1
    request_body = responses.calls[0].request.body
    assert request_body is not None
    body = json.loads(request_body)
    assert body["chat_id"] == "12345"
    assert body["text"] == "Short digest text."
    assert "parse_mode" not in body


@responses.activate
def test_deliver_includes_parse_mode_when_given() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/bottest-token/sendMessage",
        json={"ok": True},
        status=200,
    )
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    deliverer.deliver("<b>Hi</b>", parse_mode="HTML")

    request_body = responses.calls[0].request.body
    assert request_body is not None
    body = json.loads(request_body)
    assert body["parse_mode"] == "HTML"


@responses.activate
def test_deliver_splits_long_text_into_multiple_messages() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/bottest-token/sendMessage",
        json={"ok": True},
        status=200,
    )
    long_text = "\n".join(f"line {i}" for i in range(1000))
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    deliverer.deliver(long_text)

    assert len(responses.calls) > 1


@responses.activate
def test_deliver_raises_delivery_error_on_failure() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/bottest-token/sendMessage",
        body=requests.exceptions.ConnectionError("refused"),
    )
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    try:
        deliverer.deliver("hello")
        raise AssertionError("expected DeliveryError")
    except DeliveryError:
        pass


@responses.activate
def test_deliver_error_does_not_leak_bot_token() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/botsuper-secret-token/sendMessage",
        status=400,
    )
    deliverer = TelegramDeliverer(bot_token="super-secret-token", chat_id="12345")

    try:
        deliverer.deliver("hello")
        raise AssertionError("expected DeliveryError")
    except DeliveryError as error:
        assert "super-secret-token" not in str(error)


def test_chunk_message_returns_single_chunk_when_short() -> None:
    assert _chunk_message("short") == ["short"]


@responses.activate
def test_get_updates_returns_result_list() -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/bottest-token/getUpdates",
        json={
            "ok": True,
            "result": [{"update_id": 1, "message": {"text": "approve example.com"}}],
        },
        status=200,
    )
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    updates = deliverer.get_updates(offset=None)

    assert len(updates) == 1
    assert updates[0]["update_id"] == 1


@responses.activate
def test_get_updates_sends_offset_when_given() -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/bottest-token/getUpdates",
        json={"ok": True, "result": []},
        status=200,
    )
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    deliverer.get_updates(offset=7)

    request_url = responses.calls[0].request.url
    assert request_url is not None
    query = parse_qs(urlparse(request_url).query)
    assert query["offset"] == ["7"]


@responses.activate
def test_get_updates_raises_delivery_error_on_failure() -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/bottest-token/getUpdates",
        body=requests.exceptions.ConnectionError("refused"),
    )
    deliverer = TelegramDeliverer(bot_token="test-token", chat_id="12345")

    try:
        deliverer.get_updates(offset=None)
        raise AssertionError("expected DeliveryError")
    except DeliveryError:
        pass


@responses.activate
def test_get_updates_error_does_not_leak_bot_token() -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/botsuper-secret-token/getUpdates",
        status=400,
    )
    deliverer = TelegramDeliverer(bot_token="super-secret-token", chat_id="12345")

    try:
        deliverer.get_updates(offset=None)
        raise AssertionError("expected DeliveryError")
    except DeliveryError as error:
        assert "super-secret-token" not in str(error)


def test_chunk_message_splits_on_line_boundaries() -> None:
    text = "\n".join(f"line-{i}" for i in range(600))

    chunks = _chunk_message(text, max_length=50)

    assert len(chunks) > 1
    assert all(len(chunk) <= 50 for chunk in chunks)
    # Reassembling preserves every line, in order, none dropped.
    assert "\n".join(chunks).split("\n") == text.split("\n")
