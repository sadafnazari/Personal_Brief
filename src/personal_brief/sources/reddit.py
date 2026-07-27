"""Reddit source — powers the Trends pillar.

Uses Reddit's public JSON endpoints (``<subreddit>/hot.json``), which need no
authentication for read-only access. Reddit does rate-limit aggressively for
generic User-Agents, so a descriptive one is sent by default.
"""

from __future__ import annotations

from datetime import UTC, datetime

import requests

from personal_brief.models import Item, Pillar
from personal_brief.sources import SourceError

DEFAULT_MAX_ITEMS = 10
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_USER_AGENT = "personal-brief/0.1 (personal daily-digest hobby project)"


class RedditSource:
    """Fetches hot posts from a single subreddit, filtered by a minimum upvote count."""

    def __init__(
        self,
        subreddit: str,
        min_upvotes: int,
        max_items: int = DEFAULT_MAX_ITEMS,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.subreddit = subreddit
        self.min_upvotes = min_upvotes
        self.max_items = max_items
        self.user_agent = user_agent
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        """Fetch hot posts and return those at or above ``min_upvotes``.

        Raises:
            SourceError: if the subreddit cannot be reached or returns an unexpected shape.
        """
        url = f"https://www.reddit.com/r/{self.subreddit}/hot.json"
        try:
            response = requests.get(
                url,
                params={"limit": 25},
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise SourceError(f"Could not fetch r/{self.subreddit}: {error}") from error

        try:
            children = response.json()["data"]["children"]
            posts = [child["data"] for child in children]
        except (ValueError, KeyError, TypeError) as error:
            raise SourceError(
                f"Unexpected response from Reddit for r/{self.subreddit}: {error}"
            ) from error

        filtered = [post for post in posts if post.get("ups", 0) >= self.min_upvotes]
        return [self._to_item(post) for post in filtered[: self.max_items]]

    def _to_item(self, post: dict[str, object]) -> Item:
        permalink = post.get("permalink")
        url = f"https://www.reddit.com{permalink}" if permalink else str(post.get("url", ""))
        created_utc = post.get("created_utc")
        published_at = (
            datetime.fromtimestamp(float(created_utc), tz=UTC)
            if isinstance(created_utc, int | float)
            else None
        )
        ups = post.get("ups")
        return Item(
            pillar=Pillar.TRENDS,
            source=f"r/{self.subreddit}",
            external_id=str(post.get("id") or url),
            title=str(post.get("title") or "(untitled)"),
            url=url,
            published_at=published_at,
            author=str(post["author"]) if post.get("author") else None,
            body=str(post.get("selftext", ""))[:500],
            score=int(ups) if isinstance(ups, int) else None,
        )
