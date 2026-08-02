# Personal Brief

A personal assistant that follows the people and trends worth your attention and delivers a daily brief, so you stop feeling left behind without spending time hunting.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![CI](https://github.com/sadafnazari/Personal_Brief/actions/workflows/ci.yml/badge.svg)
![Daily brief](https://github.com/sadafnazari/Personal_Brief/actions/workflows/daily-brief.yml/badge.svg)

Personal Brief watches the sources you trust and the places new ideas surface, then sends you one concise digest a day. Three pillars:

- **Follow**: track specific people (blogs, newsletters) and summarize their new posts.
- **Trends**: surface what is gaining traction right now (Hacker News, Reddit, and more).
- **Discover**: proactively suggest new voices adjacent to the ones you already value.

## Quickstart

```bash
# 1. Create an environment (conda shown; any venv works)
conda create -n personal_brief python=3.12
conda activate personal_brief

# 2. Install the project and dev tools
pip install -e ".[dev]"

# 3. Make it yours: edit the control panel
$EDITOR config/sources.yaml

# 4. Install Ollama (free, local summarizer) on Linux/WSL
sudo apt-get update && sudo apt-get install -y zstd  # required by the installer below
curl -fsSL https://ollama.com/install.sh | sh
# macOS/Windows: download from https://ollama.com/download instead

# 5. Start Ollama (skip if it's already running as a service) and pull a model
ollama serve &
ollama pull llama3.1

# 6. Run
python -m personal_brief run
```

Each run fetches new posts from your Follow sources plus Hacker News and Reddit trends, summarizes anything you haven't seen yet, and writes a dated digest to `data/digests/YYYY-MM-DD.html` (open it in a browser), grouped into Following, Trending, and Discover sections. It also delivers the digest via Telegram if configured. Items you've already seen are skipped on the next run.

If `discover.enabled: true` in `config/sources.yaml`, each run also looks for domains that keep showing up in your Trends items but aren't followed yet. Once a domain crosses `discover.min_sightings`, it's suggested in your Telegram digest. Reply `approve <domain>` to start following it (its feed is auto-detected where possible) or `reject <domain>` to dismiss it for good. You can also skip suggestions entirely and add any feed on the spot: reply `follow <name> <rss-url>` (for example `follow Kyle Kingsbury https://aphyr.com/posts.atom`) and it's validated and added immediately. Either way you get a confirmation message back. Authors added through Telegram show up under Following automatically.

> **Reddit caveat:** Reddit's public JSON endpoint may block requests from some networks with a 403 (see [`docs/known-issues.md`](docs/known-issues.md) for detail). If that happens, that subreddit is skipped and everything else still works normally.

## Configuration

Everything you tune lives in [`config/sources.yaml`](config/sources.yaml): the people to follow, the trend thresholds, which summarizer to use, and where to deliver. You edit that file, you never touch the code.

Secrets (Telegram token, optional Claude or Groq API key, Turso credentials) go in a `.env` file. Copy [`.env.example`](.env.example) and fill in whichever you need. `.env` is gitignored.

## Scheduling

Personal Brief can also run on its own every day via GitHub Actions ([`.github/workflows/daily-brief.yml`](.github/workflows/daily-brief.yml)), entirely on free tiers. To enable it, once the repo is on GitHub, add these as repository secrets:

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
- `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` (a free database at [turso.tech](https://turso.tech))
- `GROQ_API_KEY` (a free key at [console.groq.com/keys](https://console.groq.com/keys))

See [`docs/architecture.md`](docs/architecture.md) for how the scheduled run differs from a local one.

## Architecture

A small, pluggable pipeline: sources feed a dedupe store, which feeds a summarizer, which feeds delivery. Full design rationale, the protocol each stage implements, and how to extend it: **[`docs/architecture.md`](docs/architecture.md)**.

Known problems being tracked for later: **[`docs/known-issues.md`](docs/known-issues.md)**.

## Development

```bash
ruff format src tests && ruff check src tests   # lint + format
mypy src tests                                  # type check
pytest -q tests                                 # tests
pre-commit install                              # run all of the above on every commit
```

See [`CLAUDE.md`](CLAUDE.md) for the full set of project conventions.

## Roadmap

- [x] Project scaffold, config, SQLite store
- [x] RSS ingest, Ollama summary, local HTML digest
- [x] Hacker News and Reddit trends, grouped digest sections
- [x] Telegram delivery
- [x] Discover pillar (suggest and approve)
- [x] Scheduling (GitHub Actions, hosted summarizer, hosted database)

## License

[MIT](LICENSE)
