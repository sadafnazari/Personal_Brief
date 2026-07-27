from __future__ import annotations

from typing import Any

import pytest

from personal_brief.store import _as_http_url, _TursoBackend


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("libsql://personalbrief-me.turso.io", "https://personalbrief-me.turso.io"),
        ("wss://personalbrief-me.turso.io", "https://personalbrief-me.turso.io"),
        ("ws://personalbrief-me.turso.io", "http://personalbrief-me.turso.io"),
        ("https://personalbrief-me.turso.io", "https://personalbrief-me.turso.io"),
        ("http://personalbrief-me.turso.io", "http://personalbrief-me.turso.io"),
    ],
)
def test_as_http_url_rewrites_websocket_schemes(given: str, expected: str) -> None:
    assert _as_http_url(given) == expected


def test_backend_closes_client_and_reraises_when_schema_init_fails(monkeypatch: Any) -> None:
    closed = False

    class _FakeClient:
        def batch(self, statements: list[str]) -> None:
            raise RuntimeError("handshake failed")

        def close(self) -> None:
            nonlocal closed
            closed = True

    def _fake_create_client_sync(url: str, auth_token: str) -> _FakeClient:
        assert url.startswith("https://")  # confirms the scheme was rewritten
        return _FakeClient()

    import libsql_client

    monkeypatch.setattr(libsql_client, "create_client_sync", _fake_create_client_sync)

    with pytest.raises(RuntimeError, match="handshake failed"):
        _TursoBackend(url="libsql://personalbrief-me.turso.io", auth_token="token")

    assert closed is True
