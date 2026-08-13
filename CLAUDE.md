# Personal Brief — Project Instructions

Extends `~/.claude/CLAUDE.md`. This file holds only what a human reader of the
README doesn't need and a hook can't enforce: architectural boundaries and
decisions already settled, so they aren't re-litigated each session.

**Everything user-facing lives in [`README.md`](README.md) and is not repeated
here** — what the project is, quickstart, configuration, scheduling, the dev
commands, and the authoritative current phase (README → Roadmap). Design
rationale: [`docs/architecture.md`](docs/architecture.md). Open problems:
[`docs/known-issues.md`](docs/known-issues.md) — check there before assuming a
source failure is a new bug (Reddit was dropped entirely as a Trends source
after its anonymous JSON API proved unfixably 403-blocked).

## Enforced automatically — don't restate these as rules

[`.claude/settings.json`](.claude/settings.json) wires four hooks in
[`.claude/hooks/`](.claude/hooks/). They are the enforcement; this list is just
a map so you know what will fire.

| Hook | When | Effect |
| --- | --- | --- |
| `format_python.py` | after writing `src/**` or `tests/**` `.py` | runs `ruff format` + `ruff check --fix` on that file |
| `quality_gates.py` | end of turn, if Python changed | strict `mypy` then `pytest` — **blocks** the turn on failure |
| `guard_bash.py` | before any Bash | denies `pytest`/`mypy`/`ruff`/`pip` outside `conda run -n personal_brief`; denies a Claude co-author trailer; asks before `git commit`/`git push` |
| `dependency_reminder.py` | after editing `pyproject.toml` | injects the "re-run `pip install -e '.[dev]'`" reminder |

`mypy` runs in **strict** mode. If a third-party dependency ships no type stubs
(e.g. `feedparser`), add a narrowly scoped `[[tool.mypy.overrides]]` block in
`pyproject.toml` — never loosen strictness project-wide.

## Beyond the gates

Unit tests passing is necessary but has not been sufficient in this project —
the Reddit 403 was only ever caught by a real run. **Before declaring a phase
done, do one genuine end-to-end run** against the real feeds / real Ollama /
real APIs, and actually read the output file.

## Dependencies

`pyproject.toml` is the single source of dependency truth — no
`requirements.txt`, no committed conda env file. Runtime deps go in
`[project.dependencies]`; lint/test-only deps in
`[project.optional-dependencies].dev`. **Ask before adding one** — prefer a
small hand-written helper over a dependency for something trivial (see
`env.py`'s `.env` loader, written instead of adding `python-dotenv`).

## Architectural rules — keep the plugin boundaries intact

- **New source** = one new file under `src/personal_brief/sources/`
  implementing the `Source` protocol (`fetch() -> list[Item]`, raising
  `SourceError` on failure) + one addition to `cli._build_sources()`. Don't let
  other stages know about a specific source.
- **New summarizer** = one new file under `summarize/` implementing the
  `Summarizer` protocol (`summarize(items) -> str`, raising `SummarizerError`)
  + one branch in `summarize.create_summarizer()`.
- **New delivery channel** = one new file under `deliver/` implementing the
  `Deliverer` protocol (`deliver(text) -> None`, raising `DeliveryError`) + one
  branch in `deliver.create_deliverer()`.
- **`config/sources.yaml` is the only user-facing control surface.** Never
  hardcode a follow list, a threshold, or a provider choice — it goes in the
  YAML and a corresponding field in `config.py`'s dataclasses.
- **Secrets never go in YAML.** They're read from the environment (`.env`,
  loaded by `env.py`) — see `.env.example` for the current set.
- **Error-handling severity is a deliberate per-stage decision, not an
  accident:** a source failing logs a warning and the run continues; a
  summarizer failing aborts the run (nothing useful to deliver); a delivery
  failure logs and the run still succeeds (the local HTML digest already exists
  as a fallback). Preserve this when adding new stages or branches.

## Testing conventions

- Mock HTTP with the `responses` library (already a dev dependency) — see
  `tests/test_hackernews_source.py` / `test_ollama_summarizer.py`.
- RSS/feed fixtures live in `tests/fixtures/`.
- One test module per source file, named `test_<source>_source.py`.
