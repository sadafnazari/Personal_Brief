from __future__ import annotations

import pytest

from personal_brief.config import SummarizerConfig
from personal_brief.summarize import SummarizerError, create_summarizer
from personal_brief.summarize.ollama import OllamaSummarizer


def test_create_summarizer_ollama() -> None:
    summarizer = create_summarizer(SummarizerConfig(provider="ollama", model="llama3.1"))

    assert isinstance(summarizer, OllamaSummarizer)
    assert summarizer.model == "llama3.1"


def test_create_summarizer_ollama_defaults_model() -> None:
    summarizer = create_summarizer(SummarizerConfig(provider="ollama", model=None))

    assert isinstance(summarizer, OllamaSummarizer)
    assert summarizer.model == "llama3.1"


def test_create_summarizer_claude_not_yet_implemented() -> None:
    with pytest.raises(SummarizerError, match="not implemented yet"):
        create_summarizer(SummarizerConfig(provider="claude", model=None))
