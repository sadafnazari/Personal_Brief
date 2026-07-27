from __future__ import annotations

from pathlib import Path

import pytest

from personal_brief.config import ConfigError, load_config

_VALID_YAML = """
interests:
  - software architecture
follow:
  - name: Martin Fowler
    rss: https://martinfowler.com/feed.atom
trends:
  hackernews:
    min_points: 120
  reddit:
    subreddits: [programming, ExperiencedDevs]
    min_upvotes: 150
summarizer:
  provider: ollama
  model: llama3.1
delivery:
  telegram: true
discover:
  enabled: true
  min_sightings: 5
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_config_parses_all_sections(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, _VALID_YAML))

    assert config.interests == ("software architecture",)
    assert len(config.follow) == 1
    assert config.follow[0].name == "Martin Fowler"
    assert config.trends.hackernews is not None
    assert config.trends.hackernews.min_points == 120
    assert config.trends.reddit is not None
    assert config.trends.reddit.subreddits == ("programming", "ExperiencedDevs")
    assert config.summarizer.provider == "ollama"
    assert config.delivery.telegram is True
    assert config.discover.enabled is True
    assert config.discover.min_sightings == 5


def test_discover_defaults_when_section_omitted(tmp_path: Path) -> None:
    yaml_without_discover = _VALID_YAML.split("discover:")[0]
    config = load_config(_write(tmp_path, yaml_without_discover))

    assert config.discover.enabled is False
    assert config.discover.min_sightings == 3


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")


def test_invalid_provider_raises(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("provider: ollama", "provider: gpt4")
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, bad))
