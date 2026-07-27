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

**What we don't yet know:** whether it also 403s from a real WSL/home
network. Cloud/datacenter IP ranges are the documented target of Reddit's
block; a home residential IP is a different case and may work fine.
**First step when picking this up: just run `personal-brief run` from the
real machine and check the log for `r/...` warnings.**

**Options if it's blocked from home too, roughly in order of effort:**

1. **Do nothing.** Accept degraded Reddit coverage — Follow and Hacker News
   still work. Simplest, and may be moot if the home network isn't blocked.
2. **Authenticated Reddit API (PRAW).** Register a free Reddit "script" app,
   use OAuth client credentials instead of the anonymous JSON endpoint. More
   reliable, but adds a secret to manage and a new dependency (`praw`).
3. **Alternate free trend source instead of Reddit** — e.g. lobste.rs (has a
   JSON API, smaller community but similar spirit), or drop Reddit and lean
   on Hacker News plus more RSS feeds.
4. **A proxy/relay.** Adds infrastructure and cost; not worth it for a hobby
   project.

**Recommendation when picking this up:** try option 1 (just test from home)
before spending effort on 2 or 3.

<!-- Add new entries above this line as they're found. -->
