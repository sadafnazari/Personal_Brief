# Personal Brief — Project Instructions

Read this before touching the code. It extends the global instructions in
`~/.claude/CLAUDE.md` with project-specific conventions, current status, and
things that have already been decided so they aren't re-litigated each
session.

## What this is

A personal, config-driven daily digest: follows specific people (RSS),
surfaces trends (Hacker News), and will eventually suggest new voices to
follow (Discover pillar). Free by default (Ollama, local), with Claude as an
opt-in paid swap. Full design rationale:
[`docs/architecture.md`](docs/architecture.md). Open problems:
[`docs/known-issues.md`](docs/known-issues.md) — check there before assuming
a source failure is a new bug (e.g. Reddit was dropped entirely as a Trends
source after its anonymous JSON API proved unfixably 403-blocked; see that
file's history).

## Environment

- The user develops in a **conda env named `personal_brief`** (already
  created on their machine). Use `conda run -n personal_brief <cmd>` to
  install/verify against it directly rather than creating a throwaway venv —
  it keeps their real environment current so they can immediately run
  whatever was just built.
- **`pyproject.toml` is the single source of dependency truth.** No
  `requirements.txt`, no committed conda env file. Runtime deps go in
  `[project.dependencies]`; anything only needed for linting/testing goes in
  `[project.optional-dependencies].dev`.
- **Whenever a dependency is added or changed, say so explicitly** and remind
  that `pip install -e ".[dev]"` must be re-run in the conda env — editable
  installs pick up code changes automatically but not new dependencies. This
  has bitten the user once already (Phase 1 → Phase 2 handoff).
- **Ask before adding a new dependency** (per the global rule) — prefer a
  small hand-written helper over a dependency for something trivial (see
  `env.py`'s `.env` loader, written instead of adding `python-dodotenv`).

## Quality gates — required before calling anything done

Run all four, in this order, via the conda env:

```bash
conda run -n personal_brief ruff format src tests
conda run -n personal_brief ruff check src tests
conda run -n personal_brief mypy src tests
conda run -n personal_brief pytest -q tests
```

`mypy` runs in **strict** mode and must stay clean. If a third-party
dependency ships no type stubs (e.g. `feedparser`), add a narrowly scoped
`[[tool.mypy.overrides]]` block in `pyproject.toml` — never loosen strictness
project-wide.

**Beyond unit tests, do one real end-to-end run before declaring a phase
done** — the pattern used in every phase so far: build/verify against a
fixture or a mocked HTTP layer first, then (when feasible) a genuine run
against the real feeds / real Ollama / real APIs, and actually read the
output file. Unit tests passing is necessary but has not been sufficient by
itself to catch real issues in this project (the Reddit 403 was only found
this way).

## Architectural rules — keep the plugin boundaries intact

- **New source** = one new file under `src/personal_brief/sources/`
  implementing the `Source` protocol (`fetch() -> list[Item]`, raising
  `SourceError` on failure) + one addition to `cli._build_sources()`. Don't
  let other stages know about a specific source.
- **New summarizer** = one new file under `summarize/` implementing the
  `Summarizer` protocol (`summarize(items) -> str`, raising
  `SummarizerError` on failure) + one branch in
  `summarize.create_summarizer()`.
- **New delivery channel** = one new file under `deliver/` implementing the
  `Deliverer` protocol (`deliver(text) -> None`, raising `DeliveryError` on
  failure) + one branch in `deliver.create_deliverer()`.
- **`config/sources.yaml` is the only user-facing control surface.** Never
  hardcode a follow list, a threshold, or a provider choice — it goes in the
  YAML and a corresponding field in `config.py`'s dataclasses.
- **Secrets never go in YAML.** They're read from the environment (`.env`,
  loaded by `env.py`) — see `.env.example` for the current set.
- **Error-handling severity is a deliberate per-stage decision, not an
  accident:** a source failing logs a warning and the run continues; a
  summarizer failing aborts the run (nothing useful to deliver); a delivery
  failure logs and the run still succeeds (the local HTML digest already
  exists as a fallback). Preserve this when adding new stages/branches.

## Testing conventions

- Mock HTTP with the `responses` library (already a dev dependency) — see
  `tests/test_hackernews_source.py` / `test_ollama_summarizer.py` for the
  pattern.
- RSS/feed fixtures live in `tests/fixtures/`.
- One test module per source file, named `test_<source>_source.py`.

## Git

- **Never commit or push unless explicitly asked** — this repo has not been
  `git init`'d yet as of Phase 2; confirm with the user before doing so.

## Status

Kept in sync with the README roadmap — check `README.md` → Roadmap for the
authoritative current phase. Update both when a phase completes.
