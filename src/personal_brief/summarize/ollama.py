"""Free, local summarizer backed by Ollama (https://ollama.com).

Requires Ollama running locally (``ollama serve``, on by default after install)
with the configured model pulled (``ollama pull llama3.1``).
"""

from __future__ import annotations

from collections.abc import Sequence

import requests

from personal_brief.models import Item
from personal_brief.summarize import SummarizerError

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 120.0


class OllamaSummarizer:
    """Summarizes items using a locally running Ollama model."""

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def summarize(self, items: Sequence[Item]) -> str:
        """Summarize ``items`` into a short digest via the local Ollama API."""
        if not items:
            return "Nothing new today."

        prompt = _build_prompt(items)
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as error:
            raise SummarizerError(
                f"Could not reach Ollama at {self.base_url}. Is it running? "
                f"(`ollama serve`, and `ollama pull {self.model}`.) Details: {error}"
            ) from error
        except requests.exceptions.RequestException as error:
            raise SummarizerError(f"Ollama request failed: {error}") from error

        try:
            text = response.json()["response"]
        except (ValueError, KeyError) as error:
            raise SummarizerError(f"Unexpected response from Ollama: {error}") from error

        return str(text).strip()


def _build_prompt(items: Sequence[Item]) -> str:
    entries = "\n\n".join(
        f"- {item.title} (by {item.author or item.source})\n  {item.url}\n  {item.body[:500]}"
        for item in items
    )
    return (
        "You are writing a short, friendly daily digest for one reader who follows "
        "these authors. Summarize the new posts below in a few sentences each, "
        "grouped naturally, in plain prose. Do not invent details not present in "
        "the text. Skip a post entirely if there isn't enough content to summarize.\n\n"
        f"{entries}"
    )
