"""Free CI summarizer backed by Groq (https://console.groq.com/docs).

Authenticates with a Groq API key (``GROQ_API_KEY``) — a free account with no
credit card required. The API is OpenAI-compatible, so the request/response
shape mirrors any other ``chat/completions`` backend.
"""

from __future__ import annotations

from collections.abc import Sequence

import requests

from personal_brief.models import Item
from personal_brief.summarize import SummarizerError, build_prompt

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_TIMEOUT_SECONDS = 120.0


class GroqSummarizer:
    """Summarizes items using a model hosted on Groq."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def summarize(self, items: Sequence[Item]) -> str:
        """Summarize ``items`` into a short digest via the Groq API."""
        if not items:
            return "Nothing new today."

        prompt = build_prompt(items)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise SummarizerError(f"Groq request failed: {error}") from error

        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as error:
            raise SummarizerError(f"Unexpected response from Groq: {error}") from error

        return str(text).strip()
