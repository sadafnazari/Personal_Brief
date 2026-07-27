from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from personal_brief.digest import render_digest, render_telegram_messages, write_digest
from personal_brief.models import Item, Pillar


def _item() -> Item:
    return Item(
        pillar=Pillar.FOLLOW,
        source="Sample Blog",
        external_id="1",
        title="Hello <World>",
        url="https://example.com/1",
        author="Jane Doe",
    )


def test_render_digest_includes_summary_and_items() -> None:
    html = render_digest([_item()], "A short summary.", datetime(2026, 1, 2, tzinfo=UTC))

    assert "A short summary." in html
    assert "Jane Doe" in html
    # Title must be HTML-escaped, not raw.
    assert "Hello &lt;World&gt;" in html
    assert "<World>" not in html


def test_render_digest_handles_empty_items() -> None:
    html = render_digest([], "Nothing new.", datetime(2026, 1, 2, tzinfo=UTC))

    assert "Nothing new today." in html


def test_render_digest_groups_by_pillar_in_order() -> None:
    follow_item = _item()
    trend_item = Item(
        pillar=Pillar.TRENDS,
        source="Hacker News",
        external_id="99",
        title="Trending Thing",
        url="https://news.ycombinator.com/item?id=99",
        score=250,
    )

    html = render_digest([trend_item, follow_item], "Summary.", datetime(2026, 1, 2, tzinfo=UTC))

    assert "Following (1)" in html
    assert "Trending (1)" in html
    # Following must appear before Trending regardless of input order.
    assert html.index("Following (1)") < html.index("Trending (1)")
    # Score is rendered for trend items.
    assert "250 pts" in html


def test_render_digest_omits_empty_sections() -> None:
    html = render_digest([_item()], "Summary.", datetime(2026, 1, 2, tzinfo=UTC))

    assert "Following (1)" in html
    assert "Trending" not in html


def test_render_telegram_messages_returns_header_plus_one_per_section() -> None:
    follow_item = _item()
    trend_item = Item(
        pillar=Pillar.TRENDS,
        source="Hacker News",
        external_id="99",
        title="Trending Thing",
        url="https://news.ycombinator.com/item?id=99",
        score=250,
    )

    messages = render_telegram_messages(
        [trend_item, follow_item], "Summary.", datetime(2026, 1, 2, tzinfo=UTC)
    )

    assert len(messages) == 3
    header, following_message, trending_message = messages
    assert "<b>Personal Brief — Friday, January 02 2026</b>" in header
    assert "Summary." in header
    assert "📰 <b>Following (1)</b>" in following_message
    assert "🔥 <b>Trending (1)</b>" in trending_message
    assert "250 pts" in trending_message
    # Title is HTML-escaped and rendered as a tappable link, not raw text + URL.
    assert "Hello &lt;World&gt;" in following_message
    assert "<World>" not in following_message
    assert '<a href="https://example.com/1">' in following_message


def test_render_telegram_messages_handles_no_items() -> None:
    messages = render_telegram_messages([], "Nothing new.", datetime(2026, 1, 2, tzinfo=UTC))

    assert messages == ["<b>Personal Brief — Friday, January 02 2026</b>\n\nNothing new."]


def test_write_digest_creates_dated_file(tmp_path: Path) -> None:
    generated_at = datetime(2026, 1, 2, tzinfo=UTC)

    path = write_digest("<html></html>", tmp_path, generated_at)

    assert path == tmp_path / "digests" / "2026-01-02.html"
    assert path.read_text(encoding="utf-8") == "<html></html>"
