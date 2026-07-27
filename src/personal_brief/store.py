"""Persistence: what we have already delivered, and who we discovered.

Three small responsibilities:

* **Dedupe** — remember every item we have surfaced so a post is never sent twice.
* **Discovery log** — domain sighting counts, suggestions, and your approve/reject
  decision, so the Discover pillar (Phase 4) doesn't repeat itself or lose state
  between runs.
* **Generic key-value state** — small bits of state that don't warrant their own
  table (e.g. the Telegram reply-polling offset).

Two backends share the same schema and the same :class:`Store` interface:

* **Local SQLite** (default) — a file under the data directory
  (``PERSONAL_BRIEF_DATA_DIR``). Used for local development and testing, kept
  deliberately separate from the CI/production database so local runs can
  never mark real items as seen.
* **Turso (libSQL)** — used in CI (see ``.github/workflows/daily-brief.yml``)
  so dedupe/Discover state survives between ephemeral GitHub Actions runs.
  Selected automatically when ``TURSO_DATABASE_URL`` is set.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, cast

from personal_brief.models import Item

DEFAULT_DATA_DIR = Path("data")
DATA_DIR_ENV_VAR = "PERSONAL_BRIEF_DATA_DIR"
DATABASE_FILENAME = "personal_brief.db"

TURSO_DATABASE_URL_ENV_VAR = "TURSO_DATABASE_URL"
TURSO_AUTH_TOKEN_ENV_VAR = "TURSO_AUTH_TOKEN"

STATUS_SUGGESTED = "suggested"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS seen_items (
        dedupe_key    TEXT PRIMARY KEY,
        source        TEXT NOT NULL,
        title         TEXT,
        url           TEXT,
        first_seen_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS discovered_authors (
        name               TEXT PRIMARY KEY,
        feed_url           TEXT,
        reason             TEXT,
        status             TEXT NOT NULL DEFAULT 'suggested',
        first_suggested_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS domain_sightings (
        domain        TEXT PRIMARY KEY,
        sightings     INTEGER NOT NULL DEFAULT 0,
        last_seen_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kv_state (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
]


@dataclass(frozen=True, slots=True)
class DiscoveredAuthor:
    """An author the Discover pillar knows about, with its current status.

    ``name`` holds a domain for mined suggestions (e.g. "aphyr.com") or a
    human name for manually-added follows (e.g. "Kyle Kingsbury") — whichever
    identity that entry was created with.
    """

    name: str
    feed_url: str | None
    reason: str
    status: str


def resolve_data_dir(explicit_dir: Path | None = None) -> Path:
    """Resolve the data directory from an argument, then the env var, then the default."""
    if explicit_dir is not None:
        return explicit_dir
    from_env = os.environ.get(DATA_DIR_ENV_VAR)
    if from_env:
        return Path(from_env)
    return DEFAULT_DATA_DIR


class _Backend(Protocol):
    """The minimal query surface :class:`Store` needs from either database.

    Row values are typed ``Any`` rather than ``object`` deliberately — both
    backends return dynamically-typed row values (``sqlite3`` rows and
    ``libsql_client`` rows alike), and ``Store``'s methods convert them to
    concrete types (``int(row[0])``, ``DiscoveredAuthor(*row)``) the same way
    the stdlib ``sqlite3`` API always required.
    """

    def fetchone(self, sql: str, params: Sequence[object] = ()) -> Sequence[Any] | None: ...

    def fetchall(self, sql: str, params: Sequence[object] = ()) -> list[Sequence[Any]]: ...

    def execute(self, sql: str, params: Sequence[object] = ()) -> None: ...

    def close(self) -> None: ...


class _SqliteBackend:
    """Local, file-based backend — used for development and testing."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path)
        for statement in _SCHEMA_STATEMENTS:
            self._connection.execute(statement)
        self._connection.commit()

    def fetchone(self, sql: str, params: Sequence[object] = ()) -> Sequence[Any] | None:
        return cast("Sequence[Any] | None", self._connection.execute(sql, params).fetchone())

    def fetchall(self, sql: str, params: Sequence[object] = ()) -> list[Sequence[Any]]:
        return cast("list[Sequence[Any]]", self._connection.execute(sql, params).fetchall())

    def execute(self, sql: str, params: Sequence[object] = ()) -> None:
        self._connection.execute(sql, params)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


class _TursoBackend:
    """Hosted libSQL backend — used in CI so state survives ephemeral runners.

    Talks to Turso over the ``libsql_client`` sync client rather than the
    stdlib ``sqlite3`` module, since the database lives remotely.
    """

    def __init__(self, url: str, auth_token: str) -> None:
        import libsql_client

        self._client = libsql_client.create_client_sync(url=url, auth_token=auth_token)
        self._client.batch(_SCHEMA_STATEMENTS)

    def fetchone(self, sql: str, params: Sequence[object] = ()) -> Sequence[Any] | None:
        rows = self._client.execute(sql, params).rows
        return rows[0] if rows else None

    def fetchall(self, sql: str, params: Sequence[object] = ()) -> list[Sequence[Any]]:
        return list(self._client.execute(sql, params).rows)

    def execute(self, sql: str, params: Sequence[object] = ()) -> None:
        self._client.execute(sql, params)

    def close(self) -> None:
        self._client.close()


class Store:
    """A thin wrapper over a SQLite-compatible database for dedupe and discovery state."""

    def __init__(self, backend: _Backend) -> None:
        self._backend = backend

    @classmethod
    def open(cls, data_dir: Path | None = None) -> Store:
        """Open the database appropriate for this environment.

        Uses the hosted Turso database when ``TURSO_DATABASE_URL`` (and
        ``TURSO_AUTH_TOKEN``) are set — the case in CI — otherwise falls back
        to a local SQLite file under the resolved data directory.
        """
        turso_url = os.environ.get(TURSO_DATABASE_URL_ENV_VAR)
        if turso_url:
            auth_token = os.environ.get(TURSO_AUTH_TOKEN_ENV_VAR, "")
            return cls(_TursoBackend(url=turso_url, auth_token=auth_token))

        directory = resolve_data_dir(data_dir)
        return cls(_SqliteBackend(directory / DATABASE_FILENAME))

    def has_seen(self, dedupe_key: str) -> bool:
        """Return whether an item with this dedupe key has already been recorded."""
        row = self._backend.fetchone("SELECT 1 FROM seen_items WHERE dedupe_key = ?", (dedupe_key,))
        return row is not None

    def mark_seen(self, item: Item) -> None:
        """Record an item so it is never surfaced again."""
        self._backend.execute(
            "INSERT OR IGNORE INTO seen_items "
            "(dedupe_key, source, title, url, first_seen_at) VALUES (?, ?, ?, ?, ?)",
            (item.dedupe_key, item.source, item.title, item.url, _now_iso()),
        )

    def filter_unseen(self, items: Iterable[Item]) -> list[Item]:
        """Return only the items we have not recorded yet, preserving order."""
        return [item for item in items if not self.has_seen(item.dedupe_key)]

    def seen_count(self) -> int:
        """Return how many items have been recorded so far."""
        row = self._backend.fetchone("SELECT COUNT(*) FROM seen_items")
        return int(row[0]) if row else 0

    def record_domain_sighting(self, domain: str) -> int:
        """Increment the sighting count for ``domain`` and return the new total."""
        self._backend.execute(
            "INSERT INTO domain_sightings (domain, sightings, last_seen_at) "
            "VALUES (?, 1, ?) "
            "ON CONFLICT(domain) DO UPDATE SET "
            "sightings = sightings + 1, last_seen_at = excluded.last_seen_at",
            (domain, _now_iso()),
        )
        row = self._backend.fetchone(
            "SELECT sightings FROM domain_sightings WHERE domain = ?", (domain,)
        )
        return int(row[0]) if row else 0

    def is_known_domain(self, domain: str) -> bool:
        """Return whether ``domain`` has already been suggested, approved, or rejected."""
        row = self._backend.fetchone("SELECT 1 FROM discovered_authors WHERE name = ?", (domain,))
        return row is not None

    def create_suggestion(self, domain: str, feed_url: str | None, reason: str) -> None:
        """Record a new Discover suggestion for ``domain`` with status 'suggested'."""
        self._backend.execute(
            "INSERT OR IGNORE INTO discovered_authors "
            "(name, feed_url, reason, status, first_suggested_at) VALUES (?, ?, ?, ?, ?)",
            (domain, feed_url, reason, STATUS_SUGGESTED, _now_iso()),
        )

    def get_pending_suggestions(self) -> list[DiscoveredAuthor]:
        """Return every suggestion still awaiting an approve/reject decision."""
        rows = self._backend.fetchall(
            "SELECT name, feed_url, reason, status FROM discovered_authors WHERE status = ?",
            (STATUS_SUGGESTED,),
        )
        return [DiscoveredAuthor(*row) for row in rows]

    def update_suggestion_status(self, domain: str, status: str) -> None:
        """Set the approve/reject decision for a previously suggested domain."""
        self._backend.execute(
            "UPDATE discovered_authors SET status = ? WHERE name = ?", (status, domain)
        )

    def get_approved_authors(self) -> list[DiscoveredAuthor]:
        """Return every domain approved via Discover, for merging into Follow sources."""
        rows = self._backend.fetchall(
            "SELECT name, feed_url, reason, status FROM discovered_authors "
            "WHERE status = ? AND feed_url IS NOT NULL",
            (STATUS_APPROVED,),
        )
        return [DiscoveredAuthor(*row) for row in rows]

    def add_approved_author(self, name: str, feed_url: str, reason: str) -> None:
        """Add (or replace) an author as already-approved — no suggest/approve step.

        Used for manually adding a Follow source via a Telegram ``follow``
        command, where the user has already made the decision.
        """
        self._backend.execute(
            "INSERT INTO discovered_authors "
            "(name, feed_url, reason, status, first_suggested_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "feed_url = excluded.feed_url, reason = excluded.reason, status = excluded.status",
            (name, feed_url, reason, STATUS_APPROVED, _now_iso()),
        )

    def get_update_offset(self) -> int | None:
        """Return the last processed Telegram update id, or ``None`` if never polled."""
        row = self._backend.fetchone(
            "SELECT value FROM kv_state WHERE key = 'telegram_update_offset'"
        )
        return int(row[0]) if row else None

    def set_update_offset(self, offset: int) -> None:
        """Persist the Telegram update id to resume polling from next time."""
        self._backend.execute(
            "INSERT INTO kv_state (key, value) VALUES ('telegram_update_offset', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(offset),),
        )

    def close(self) -> None:
        """Close the underlying database connection."""
        self._backend.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
