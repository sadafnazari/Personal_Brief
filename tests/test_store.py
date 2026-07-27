from __future__ import annotations

from datetime import datetime
from pathlib import Path

from personal_brief.models import Item, Pillar
from personal_brief.store import Store


def _item(external_id: str) -> Item:
    return Item(
        pillar=Pillar.FOLLOW,
        source="Test Source",
        external_id=external_id,
        title=f"Title {external_id}",
        url=f"https://example.com/{external_id}",
        published_at=datetime(2026, 1, 1),
        author="Someone",
    )


def test_mark_and_detect_seen(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        item = _item("a")
        assert store.has_seen(item.dedupe_key) is False
        store.mark_seen(item)
        assert store.has_seen(item.dedupe_key) is True
        assert store.seen_count() == 1


def test_filter_unseen_preserves_order_and_excludes_known(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        first, second, third = _item("1"), _item("2"), _item("3")
        store.mark_seen(second)
        unseen = store.filter_unseen([first, second, third])
        assert [item.external_id for item in unseen] == ["1", "3"]


def test_record_domain_sighting_increments_across_calls(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        assert store.record_domain_sighting("example.com") == 1
        assert store.record_domain_sighting("example.com") == 2
        assert store.record_domain_sighting("other.com") == 1


def test_create_suggestion_and_get_pending_suggestions(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion("example.com", feed_url="https://example.com/feed", reason="x")

        pending = store.get_pending_suggestions()

        assert len(pending) == 1
        assert pending[0].name == "example.com"
        assert pending[0].feed_url == "https://example.com/feed"
        assert pending[0].status == "suggested"
        assert store.is_known_domain("example.com") is True
        assert store.is_known_domain("unknown.com") is False


def test_update_suggestion_status_moves_out_of_pending(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion("example.com", feed_url="https://example.com/feed", reason="x")

        store.update_suggestion_status("example.com", "approved")

        assert store.get_pending_suggestions() == []
        approved = store.get_approved_authors()
        assert len(approved) == 1
        assert approved[0].name == "example.com"


def test_get_approved_authors_excludes_suggestions_without_a_feed_url(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.create_suggestion("example.com", feed_url=None, reason="no feed found")
        store.update_suggestion_status("example.com", "approved")

        assert store.get_approved_authors() == []


def test_add_approved_author_is_immediately_approved(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        store.add_approved_author(
            "Kyle Kingsbury", "https://aphyr.com/posts.atom", reason="added manually via Telegram"
        )

        assert store.get_pending_suggestions() == []
        approved = store.get_approved_authors()
        assert len(approved) == 1
        assert approved[0].name == "Kyle Kingsbury"
        assert approved[0].feed_url == "https://aphyr.com/posts.atom"


def test_add_approved_author_replaces_an_existing_entry_with_the_same_name(
    tmp_path: Path,
) -> None:
    with Store.open(tmp_path) as store:
        store.add_approved_author("Kyle Kingsbury", "https://old-url.example/feed", reason="v1")
        store.add_approved_author("Kyle Kingsbury", "https://aphyr.com/posts.atom", reason="v2")

        approved = store.get_approved_authors()
        assert len(approved) == 1
        assert approved[0].feed_url == "https://aphyr.com/posts.atom"


def test_update_offset_round_trips(tmp_path: Path) -> None:
    with Store.open(tmp_path) as store:
        assert store.get_update_offset() is None
        store.set_update_offset(42)
        assert store.get_update_offset() == 42
        store.set_update_offset(43)
        assert store.get_update_offset() == 43
