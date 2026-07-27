from __future__ import annotations

import responses

from personal_brief.models import Item, Pillar
from personal_brief.summarize import SummarizerError
from personal_brief.summarize.github_models import DEFAULT_BASE_URL, GitHubModelsSummarizer


def _item() -> Item:
    return Item(
        pillar=Pillar.FOLLOW,
        source="Sample Blog",
        external_id="1",
        title="A Great Post",
        url="https://example.com/1",
        author="Jane Doe",
        body="Some content about software design.",
    )


@responses.activate
def test_summarize_returns_model_response() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/chat/completions",
        json={"choices": [{"message": {"content": "Jane Doe wrote about software design."}}]},
        status=200,
    )
    summarizer = GitHubModelsSummarizer(model="openai/gpt-4o-mini", token="fake-token")

    result = summarizer.summarize([_item()])

    assert result == "Jane Doe wrote about software design."


def test_summarize_returns_placeholder_for_no_items() -> None:
    summarizer = GitHubModelsSummarizer(model="openai/gpt-4o-mini", token="fake-token")

    assert summarizer.summarize([]) == "Nothing new today."


@responses.activate
def test_summarize_raises_summarizer_error_on_request_failure() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/chat/completions",
        json={"error": "rate limited"},
        status=429,
    )
    summarizer = GitHubModelsSummarizer(model="openai/gpt-4o-mini", token="fake-token")

    try:
        summarizer.summarize([_item()])
        raise AssertionError("expected SummarizerError")
    except SummarizerError as error:
        assert "GitHub Models" in str(error)


@responses.activate
def test_summarize_raises_summarizer_error_on_unexpected_response_shape() -> None:
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}/chat/completions",
        json={"unexpected": "shape"},
        status=200,
    )
    summarizer = GitHubModelsSummarizer(model="openai/gpt-4o-mini", token="fake-token")

    try:
        summarizer.summarize([_item()])
        raise AssertionError("expected SummarizerError")
    except SummarizerError as error:
        assert "Unexpected response" in str(error)
