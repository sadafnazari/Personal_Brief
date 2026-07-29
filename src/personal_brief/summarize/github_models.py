"""Free CI summarizer backed by GitHub Models (https://docs.github.com/en/github-models).

Authenticates with a token that has ``models: read`` permission — in GitHub
Actions this is the workflow's own ``GITHUB_TOKEN`` (see
``.github/workflows/daily-brief.yml``); locally it can be a personal access
token with the same scope. No separate account or API key to manage.
"""

from __future__ import annotations

from collections.abc import Sequence

import requests

from personal_brief.models import Item
from personal_brief.summarize import SummarizerError, build_prompt

DEFAULT_BASE_URL = "https://models.github.ai/inference"
DEFAULT_TIMEOUT_SECONDS = 120.0


class GitHubModelsSummarizer:
    """Summarizes items using a model hosted on GitHub Models."""

    def __init__(
        self,
        model: str,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def summarize(self, items: Sequence[Item]) -> str:
        """Summarize ``items`` into a short digest via the GitHub Models API."""
        if not items:
            return "Nothing new today."

        prompt = build_prompt(items)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise SummarizerError(f"GitHub Models request failed: {error}") from error

        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as error:
            raise SummarizerError(f"Unexpected response from GitHub Models: {error}") from error

        return str(text).strip()
