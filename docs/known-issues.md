# Known Issues

Confirmed problems that are out of scope for the phase that found them —
tracked here instead of GitHub Issues until the repo is pushed.

---

## Reddit's public JSON endpoint returns 403 from cloud/datacenter IPs

**Status:** Confirmed, unresolved. Found during Phase 2 verification (2026-07-21).

**Symptom:** `RedditSource.fetch()` raises `SourceError` with
`403 Client Error: Blocked for url: https://www.reddit.com/r/<subreddit>/hot.json`.
The CLI catches this per-source, logs a warning, and continues — the run
degrades gracefully; you just get no Reddit trends that run.

**Root cause:** Reddit blocks anonymous requests to its public JSON API from
known cloud/datacenter/hosting IP ranges — a deliberate anti-scraping policy,
not specific to this code. Confirmed during Phase 2 by testing multiple
User-Agent strings, including a real browser UA — all 403'd identically from
a cloud sandbox, while Hacker News's Algolia API succeeded over the same
network path.

**Update (2026-08-03):** Tested from a real residential connection — egress
IP traced to a home/mobile ISP (Elisa Oyj, AS719, Finland), not a
cloud/datacenter range — and the endpoint still returned 403 on all
configured subreddits. So this isn't narrowly a "datacenter IP" block as
originally assumed; Reddit's anonymous JSON endpoint appears to block more
broadly (geography, ASN reputation, and/or User-Agent/behavior heuristics).
The "maybe it's fine from home" hope is ruled out — treat this as blocked
regardless of network.

**Options, roughly in order of effort:**

1. **Do nothing.** Accept degraded Reddit coverage — Follow and Hacker News
   still work. Simplest, and current default behavior since Reddit is
   blocked regardless of network.
2. **Authenticated Reddit API (PRAW).** Register a free Reddit "script" app,
   use OAuth client credentials instead of the anonymous JSON endpoint. More
   reliable, but adds a secret to manage and a new dependency (`praw`).
3. **Alternate free trend source instead of Reddit** — e.g. lobste.rs (has a
   JSON API, smaller community but similar spirit), or drop Reddit and lean
   on Hacker News plus more RSS feeds.
4. **A proxy/relay.** Adds infrastructure and cost; not worth it for a hobby
   project.

**Decision (2026-08-03):** Reddit was dropped entirely as a Trends source
rather than pursuing option 2 (PRAW) or 3 (lobste.rs/proxy) — the 403 is
confirmed unfixable without an authenticated API or a proxy, and that
maintenance cost wasn't worth it for a hobby project. `RedditSource`,
`RedditConfig`, and the `trends.reddit` config block have been removed from
the codebase; Hacker News and Follow/RSS remain. This entry is kept as a
historical record of why there's no Reddit source in the code.

## GitHub Models was fully retired (2026-07-30) — summarizer migrated to Groq

**Status:** Resolved. Found in production (daily-brief workflow failure,
2026-08-01).

**Symptom:** The `github_models` summarizer started failing every run with
`SummarizerError: GitHub Models request failed: 410 Client Error: Gone for
url: https://models.github.ai/inference/chat/completions`.

**Root cause:** GitHub retired GitHub Models entirely on 2026-07-30 (staged
shutdown announced 2026-07-01) — the playground, model catalog, and
inference API were shut off for all customers, including existing ones. Not
a bug in this project; the free hosted API this summarizer depended on no
longer exists.

**Resolution:** Replaced `summarizer.provider: github_models` with `groq`
(`src/personal_brief/summarize/groq.py`), backed by
[Groq](https://console.groq.com/docs) — also free, no credit card, and
OpenAI-compatible so the request/response shape barely changed. Default
model is `openai/gpt-oss-20b` (Groq's own recommended migration target for
the now-deprecated `llama-3.1-8b-instant`). `daily-brief.yml`'s `models:
read` permission was dropped and replaced with a `GROQ_API_KEY` repository
secret.

**What to watch:** Groq's free tier has its own deprecation cadence (it
retired `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` in mid-2026) —
check `openai/gpt-oss-20b`'s status if this summarizer starts failing again.

<!-- Add new entries above this line as they're found. -->
