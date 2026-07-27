# Personal Brief

> A personal assistant that follows the people and trends worth your attention and delivers a daily brief — so you stop feeling left behind without spending time hunting.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![CI](https://github.com/sadafnazari/Personal_Brief/actions/workflows/ci.yml/badge.svg)
![Daily brief](https://github.com/sadafnazari/Personal_Brief/actions/workflows/daily-brief.yml/badge.svg)

Personal Brief watches the sources you trust and the places new ideas surface, then
sends you one concise digest a day. Three pillars:

- **Follow** — track specific people (blogs, newsletters) and summarize their new posts.
- **Trends** — surface what is gaining traction right now (Hacker News, Reddit, ...).
- **Discover** — proactively suggest new voices adjacent to the ones you already value.

## Quickstart

```bash
# 1. Create an environment (conda shown; any venv works)
conda create -n personal_brief python=3.12
conda activate personal_brief

# 2. Install the project and dev tools
pip install -e ".[dev]"

# 3. Make it yours — edit the control panel
$EDITOR config/sources.yaml

# 4. Install Ollama (free, local summarizer) — Linux/WSL:
sudo apt-get update && sudo apt-get install -y zstd  # required by the installer below
curl -fsSL https://ollama.com/install.sh | sh
# macOS/Windows: download from https://ollama.com/download instead

# 5. Start Ollama (skip if it's already running as a service) and pull a model
ollama serve &
ollama pull llama3.1

# 6. Run
python -m personal_brief run
```

Each run fetches new posts from your Follow sources plus Hacker News and Reddit
trends, summarizes anything you haven't seen yet, writes a dated digest to
`data/digests/YYYY-MM-DD.html` (open it in a browser), grouped into Following,
Trending, and Discover sections, and delivers it via Telegram if configured.
Already-seen items are skipped on the next run.

If `discover.enabled: true` in `config/sources.yaml`, each run also mines
your Trends items for domains that keep showing up but aren't followed yet.
Once a domain crosses `discover.min_sightings`, it's suggested in your
Telegram digest — reply `approve <domain>` to start following it (its feed
is auto-detected where possible) or `reject <domain>` to dismiss it for
good. You can also skip mining entirely and add any feed on the spot:
reply `follow <name> <rss-url>` (e.g. `follow Kyle Kingsbury https://aphyr.com/posts.atom`)
and it's validated and added immediately. Either way you get a confirmation
message back. Authors added through Telegram — mined or manual — show up
under Following automatically; they're tracked in the local database rather
than `config/sources.yaml`, since they were added via Telegram rather than
by hand.

> **Reddit caveat:** Reddit's public JSON endpoint may block requests from
> some networks with a 403 (see [`docs/known-issues.md`](docs/known-issues.md)
> for detail). If it happens, that subreddit's fetch is skipped with a logged
> warning — Follow and Hacker News still work normally.

## Configuration

Everything you tune lives in [`config/sources.yaml`](config/sources.yaml) — the
people to follow, the trend thresholds, which summarizer to use, and where to
deliver. You edit that file; you never touch the code.

Secrets (Telegram token, optional Claude API key, GitHub Models token, Turso
credentials) go in a `.env` file — copy [`.env.example`](.env.example) and
fill in whichever you need. `.env` is gitignored.

## Scheduling (GitHub Actions)

[`.github/workflows/daily-brief.yml`](.github/workflows/daily-brief.yml) runs
`personal-brief run` on a daily cron schedule, entirely on free tiers:

- **Summarizer:** [GitHub Models](https://docs.github.com/en/github-models)
  instead of Ollama — GitHub Actions runners can't realistically run a local
  model, and GitHub Models needs no separate account or secret (the
  workflow's own `GITHUB_TOKEN` authenticates it, via the `models: read`
  permission). This is CI-only — local runs still default to Ollama. Which
  config a run uses is controlled by `PERSONAL_BRIEF_CONFIG`:
  [`config/sources.ci.yaml`](config/sources.ci.yaml) is the CI copy of
  `sources.yaml` with `summarizer.provider: github_models` swapped in; keep
  the two in sync by hand if you edit `follow`/`trends`/`discover`.
- **State (dedupe + Discover):** [Turso](https://turso.tech) (hosted
  libSQL/SQLite), not the local SQLite file — GitHub Actions runners are
  ephemeral, so without a real database, every run would think everything is
  new again. `Store` picks the backend automatically: Turso when
  `TURSO_DATABASE_URL` is set (CI), local SQLite otherwise (your machine).
  Local and CI deliberately use separate databases, so testing locally can
  never mark real items as already-seen in production.

**To enable it**, once the repo is on GitHub: create a free Turso database
and add `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` as repository secrets,
alongside `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`. No secret is needed for
GitHub Models — its permission is granted in the workflow file itself.

## Architecture

A small, pluggable pipeline — sources feed a dedupe store, which feeds a
summarizer, which feeds delivery. Full design rationale, the protocol each
stage implements, and how to extend it:
**[`docs/architecture.md`](docs/architecture.md)**.

Known problems being tracked for later: **[`docs/known-issues.md`](docs/known-issues.md)**.

## Development

```bash
ruff format src tests && ruff check src tests   # lint + format
mypy src tests                                  # type check
pytest -q tests                                 # tests
pre-commit install                              # run all of the above on every commit
```

See [`CLAUDE.md`](CLAUDE.md) for the full set of project conventions (agent
instructions, but equally useful as a human contributor guide).

## Roadmap

- [x] **Phase 0** — project scaffold, config, SQLite store
- [x] **Phase 1** — RSS ingest → Ollama summary → local HTML digest
- [x] **Phase 2** — Hacker News + Reddit trends, grouped digest sections
- [x] **Phase 3** — Telegram delivery
- [x] **Phase 4** — Discover pillar (suggest-and-approve)
- [x] **Phase 5** — scheduling (GitHub Actions + GitHub Models + Turso,
      verified with a real end-to-end run — daily digest delivered via
      Telegram, dedupe state persisted in Turso)
- [x] **Phase 6** — deployment (superseded by Phase 5's GitHub Actions
      approach — no separate Docker packaging planned unless that changes)

## License

[MIT](LICENSE)
