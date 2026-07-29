"""Summarizer plugins.

The summarizer turns a batch of :class:`~personal_brief.models.Item` into a
short digest of prose. It is pluggable so the free local path (Ollama) and a
paid API path (Claude) sit behind one interface — swapping providers is a
config change, not a code change.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol

from personal_brief.config import SummarizerConfig
from personal_brief.models import Item

GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"


class Summarizer(Protocol):
    """Anything that can turn a batch of items into a digest of prose."""

    def summarize(self, items: Sequence[Item]) -> str:
        """Return a digest summarizing ``items``.

        Raises:
            SummarizerError: if the summary cannot be produced.
        """
        ...


class SummarizerError(Exception):
    """Raised when a summarizer cannot produce a summary."""


def build_prompt(items: Sequence[Item]) -> str:
    """Build the shared digest prompt used by every summarizer backend."""
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


def create_summarizer(config: SummarizerConfig) -> Summarizer:
    """Build the summarizer named by ``config.provider``.

    Raises:
        SummarizerError: if the provider is unknown or not yet implemented.
    """
    if config.provider == "ollama":
        from personal_brief.summarize.ollama import OllamaSummarizer

        return OllamaSummarizer(model=config.model or "llama3.1")

    if config.provider == "github_models":
        from personal_brief.summarize.github_models import GitHubModelsSummarizer

        token = os.environ.get(GITHUB_TOKEN_ENV_VAR)
        if not token:
            raise SummarizerError(
                f"summarizer.provider 'github_models' requires {GITHUB_TOKEN_ENV_VAR} to be "
                "set. In GitHub Actions this is provided automatically when the workflow "
                "grants 'models: read' permission; locally, use a personal access token "
                "with the same scope."
            )
        return GitHubModelsSummarizer(model=config.model or "openai/gpt-4o-mini", token=token)

    if config.provider == "claude":
        raise SummarizerError(
            "summarizer.provider 'claude' is not implemented yet — it's on the "
            "roadmap. Use 'ollama' or 'github_models' for now."
        )

    raise SummarizerError(f"Unknown summarizer.provider '{config.provider}'.")
