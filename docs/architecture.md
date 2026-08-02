# Architecture

Personal Brief is a small, pluggable pipeline:

```
sources -> store (dedupe) -> summarize -> deliver
```

Each stage only depends on the *interface* of the stage before it — never a
concrete implementation — so any piece can be swapped or extended without
touching the others. This document is the map of those interfaces; see
[`../README.md`](../README.md) for the user-facing overview and
[`known-issues.md`](known-issues.md) for open problems.

## Pipeline stages & interfaces

### 1. Sources (`src/personal_brief/sources/`)

Protocol, in `sources/__init__.py`:

```python
class Source(Protocol):
    def fetch(self) -> list[Item]: ...
```

| Source | File | Pillar | Notes |
|---|---|---|---|
| RSS/Atom | `rss.py` | Follow | via `feedparser`; caps at 5 most-recent entries/feed |
| Hacker News | `hackernews.py` | Trends | Algolia API, sorted by points descending |
| Reddit | `reddit.py` | Trends | one instance per subreddit; see [known-issues.md](known-issues.md) |

Implementations raise `SourceError` on failure. The CLI catches it **per
source** — logs a warning and continues — so one dead feed or blocked API
never kills the whole run.

**To add a source:** create `sources/<name>.py` implementing
`fetch() -> list[Item]`; wire it into `cli._build_sources()`; if it needs
user-tunable settings, extend the relevant dataclass in `config.py`; mock the
HTTP layer in tests (see `tests/test_hackernews_source.py` for the
`responses`-based pattern used throughout).

### 2. Normalization (`models.py`)

Every source converts its raw payload into an `Item` — the one shape every
downstream stage understands. `Item.pillar` (`FOLLOW` / `TRENDS` /
`DISCOVER`) drives digest grouping. `Item.dedupe_key`
(`f"{source}:{external_id}"`) is the store's identity key.

### 3. Store (`store.py`)

SQLite-compatible, three responsibilities:

- `seen_items` — dedupe. Never resurface the same item twice.
- `discovered_authors` / `domain_sightings` — the Discover pillar's
  suggest/approve log and raw sighting counts (Phase 4).
- `kv_state` — small generic state, currently just the Telegram
  reply-polling offset.

`Store.filter_unseen()` is the dedupe boundary the CLI calls between fetch
and summarize.

**Two backends** (Phase 5), selected automatically by `Store.open()`, behind
a small `_Backend` protocol (`fetchone`/`fetchall`/`execute`/`close`) so the
rest of `Store` doesn't know which one is active:

- `_SqliteBackend` — local file under `PERSONAL_BRIEF_DATA_DIR`, via stdlib
  `sqlite3`. Default; used for local development and testing.
- `_TursoBackend` — hosted libSQL via `libsql_client`, used when
  `TURSO_DATABASE_URL` is set (GitHub Actions). Needed because Actions
  runners are ephemeral — without a real remote database, every scheduled
  run would see nothing as already-seen. Deliberately a *separate* database
  from local SQLite, so local dev/test runs can never mark real items seen
  in production.

### 4. Summarizer (`summarize/`)

Protocol, in `summarize/__init__.py`:

```python
class Summarizer(Protocol):
    def summarize(self, items: Sequence[Item]) -> str: ...
```

`create_summarizer(config.summarizer)` is the factory — reads
`summarizer.provider` from YAML and returns the matching implementation.

- `ollama` — implemented, free/local, requires a running Ollama server. The
  local/interactive default.
- `groq` — implemented (Phase 5, migrated from `github_models` after GitHub
  Models was fully retired on 2026-07-30 — see `docs/known-issues.md`),
  free/hosted via [Groq](https://console.groq.com/docs), authenticated with a
  `GROQ_API_KEY`. The GitHub Actions default, set via
  `PERSONAL_BRIEF_SUMMARIZER_PROVIDER`/`PERSONAL_BRIEF_SUMMARIZER_MODEL` env
  vars in `daily-brief.yml` — CI runners can't realistically run Ollama.
- `claude` — stubbed; `create_summarizer` raises `SummarizerError` with a
  clear "not implemented yet" message rather than silently failing.

Errors raise `SummarizerError`. Unlike a source failure, a summarizer failure
**aborts the run** — there's no useful digest to deliver without a summary.

### 5. Digest (`digest.py`)

Pure rendering, no network, no state:

- `render_digest()` — groups items by pillar into sections (Following,
  Trending, Discover) and renders a self-contained HTML page with escaped
  user content.
- `write_digest()` — writes to `data/digests/YYYY-MM-DD.html`.
- `render_telegram_messages()` *(Phase 3)* — the same grouping, rendered as a
  **list** of Telegram-HTML messages: a header (bold title + AI summary),
  then one message per non-empty pillar (bold heading, an emoji, each item
  title as a tappable link) instead of one long blob. Every piece of
  user-derived text is `html.escape()`-d before being placed in a tag, the
  same pattern `render_digest()` uses for the HTML file.

### 6. Delivery (`deliver/`) — Phase 3

Protocol, in `deliver/__init__.py`:

```python
class Deliverer(Protocol):
    def deliver(self, text: str, parse_mode: str | None = None) -> None: ...
```

`parse_mode` is an optional, channel-specific formatting hint (Telegram's
`"HTML"`); it defaults to `None` (plain text) so the protocol stays backward
compatible for any implementation that ignores formatting.

`create_deliverer(config.delivery)` returns `None` when no delivery channel
is enabled, or raises `DeliveryError` if a channel is enabled but
misconfigured (e.g. Telegram enabled with no bot token in the environment).
Delivery failure is logged and **does not fail the run** — the local HTML
digest was already written, so the user always has a fallback.

- `telegram.py` — sends each of `render_telegram_messages()`'s messages as
  its own Telegram message (`parse_mode="HTML"`), each individually chunked
  to stay under Telegram's per-message length limit if needed. Discover's
  confirmation replies (`replies.py`) still send plain text — formatting was
  only requested for the digest itself.

### 7. Discover (`discover/`) — Phase 4

No new source or API calls: Discover mines the Trends items already being
fetched each run for domains worth following, entirely from data the
pipeline already has.

```
_process_discover_replies()      # poll Telegram, apply approve/reject
_build_sources()                 # config.follow + store's approved authors
_fetch_all()                     # unchanged, now may include approved authors
_mine_and_build_discover_items()  # domain-count Trends items, promote to suggestions
```

- `mining.py` — `extract_domain()` pulls the URL host off a Trends item
  (skipping HN/Reddit's own domains — self-posts aren't "a voice to follow").
  `mine()` counts sightings per unfollowed domain in `Store`; once a domain
  crosses `discover.min_sightings` (`config.py`), it's promoted to a
  suggestion via `create_suggestion()`.
- `feed_discovery.py` — best-effort RSS/Atom autodiscovery for a suggested
  domain: fetches the homepage via `requests`, parses `<link rel="alternate">`
  tags with stdlib `html.parser` (no new HTML-parsing dependency), then
  fetches and parses the feed itself via `requests` + `feedparser` for its
  title. A domain with no discoverable feed still becomes a suggestion — just
  without a ready-to-follow URL — so the user can still evaluate it manually.
- `replies.py` — `process_replies()` does one short, non-blocking
  `TelegramDeliverer.get_updates()` poll per run (offset persisted in
  `kv_state`), matching two command shapes from the configured chat:
  - `approve <domain>` / `reject <domain>` — decide a mining suggestion,
    updating `discovered_authors.status`.
  - `follow <name> <rss-url>` — add any feed directly, no mining or
    suggest/approve step involved. Validated with a real
    `RssSource(name, url).fetch()` (`sources/rss.py`) before being stored via
    `Store.add_approved_author()`, so a bad paste fails loudly instead of
    silently adding a dead source.

  Every recognized command (either shape) gets a one-line confirmation
  (`✓ Approved …` / `✓ Added "…" to Follow` / `✗ Could not add …: <reason>`),
  batched into a single Telegram message per run — a reply is never silent.

**`DiscoveredAuthor.name` is dual-purpose:** a domain for mined suggestions
(`"aphyr.com"`), a human name for manual follows (`"Kyle Kingsbury"`) —
whichever identity that row was created with. `_build_sources()` dedupes
approved authors against `config.follow` *and* against each other by
`feed_url`, so mining and manual-add can never both add the same feed twice
even though they use different keys.

**Suggestions are rendered, not dedupe-tracked.** Pending suggestions are
turned into ordinary `Item`s (`pillar=DISCOVER`) each run and merged into the
same `render_digest()` / `render_telegram_text()` call as Follow/Trends
items — no changes needed to `digest.py`, since DISCOVER-pillar grouping
already existed there. Critically, these synthetic items are **not** passed
to `store.mark_seen()`: they're stateful via `discovered_authors.status`, not
the dedupe store, so a suggestion keeps reappearing in every digest until
it's approved or rejected — unlike a Follow/Trends item, which is sent once.

**Deliberate exception to "YAML is the only control surface":** an approved
author is *not* written to `config/sources.yaml`. It's Telegram-driven, so it
lives in the store, the same way `seen_items` already does — `_build_sources()`
merges `config.follow` with `store.get_approved_authors()` every run. This is
a scoped exception for Discover specifically, not a general precedent; every
other setting (thresholds, provider choice, Follow list) still goes in YAML.

## Configuration (`config.py`)

`load_config()` reads `config/sources.yaml` into frozen dataclasses, failing
fast with a specific `ConfigError` naming the bad key. This is the only place
YAML structure is known — nothing else touches raw dicts.

**Config vs. secrets:** `config/sources.yaml` holds non-secret settings
(who to follow, thresholds, which provider). Secrets (Telegram bot token,
Claude API key) live in `.env` and are read from the environment — never
committed, never in YAML. `env.py` loads `.env` into `os.environ` at startup
(a few lines, not a dependency — see the note in that file).

## CLI (`cli.py`)

Orchestrates the stages for the `run` command:

```
_process_discover_replies()   (best-effort, if discover.enabled)
   -> _build_sources -> _fetch_all -> store.filter_unseen
   -> _mine_and_build_discover_items()   (if discover.enabled)
   -> create_summarizer().summarize()
   -> render_digest() / write_digest() -> store.mark_seen()   (Follow/Trends only)
   -> create_deliverer().deliver()   (best-effort)
```

`cli.py` has no business logic of its own — only sequencing, error handling
per stage, and logging. Each step is a thin call into the module described
above.

## Data & state

- `data/personal_brief.db` — SQLite (dedupe + discovery log). Gitignored.
- `data/digests/*.html` — one file per run date. Gitignored.

Both paths are environment-overridable (`PERSONAL_BRIEF_DATA_DIR`,
`PERSONAL_BRIEF_CONFIG`) to keep the app container-friendly ahead of Phase 6.

## Design principles (why it's built this way)

1. **One normalized type crosses every boundary** (`Item`) — sources, store,
   summarizer, and digest never know about each other's internals.
2. **Protocols, not base classes.** Structural typing (`typing.Protocol`)
   keeps implementations decoupled; nothing has to inherit from a shared
   class to plug in.
3. **Fail loud, fail scoped.** A broken feed or blocked API logs and
   continues (`SourceError`); a broken summarizer aborts the run
   (`SummarizerError`) since a digest with no summary isn't useful; a broken
   delivery channel logs and the run still succeeds, since the local digest
   is already safely written (`DeliveryError`). Config errors (`ConfigError`)
   stop before any network call.
4. **The user's control surface is YAML, not code.**
   `config/sources.yaml` is the only file a non-developer session needs to
   touch to change behavior.
5. **Free by default, paid by choice.** Ollama is the default summarizer;
   Claude is an opt-in swap via one config line, never required.
