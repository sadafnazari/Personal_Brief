"""Load and validate the user's configuration from ``config/sources.yaml``.

The YAML file is the project's control panel: it lists the people to follow, the
trend sources and thresholds, which summarizer to use, and where to deliver. This
module turns that file into typed, validated objects and fails fast — with a clear
message naming the offending key — when something is missing or malformed.

The config path is environment-overridable (``PERSONAL_BRIEF_CONFIG``) so the app
stays container-friendly. ``summarizer.provider``/``summarizer.model`` are
individually environment-overridable too (``PERSONAL_BRIEF_SUMMARIZER_PROVIDER``/
``PERSONAL_BRIEF_SUMMARIZER_MODEL``), so CI can swap in a hosted summarizer
without forking the whole config file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config/sources.yaml")
CONFIG_PATH_ENV_VAR = "PERSONAL_BRIEF_CONFIG"
SUMMARIZER_PROVIDER_ENV_VAR = "PERSONAL_BRIEF_SUMMARIZER_PROVIDER"
SUMMARIZER_MODEL_ENV_VAR = "PERSONAL_BRIEF_SUMMARIZER_MODEL"
_VALID_PROVIDERS = {"ollama", "claude", "groq"}


class ConfigError(Exception):
    """Raised when the configuration file is missing or malformed."""


@dataclass(frozen=True, slots=True)
class FollowSource:
    name: str
    rss: str


@dataclass(frozen=True, slots=True)
class HackerNewsConfig:
    min_points: int = 150


@dataclass(frozen=True, slots=True)
class RedditConfig:
    subreddits: tuple[str, ...]
    min_upvotes: int = 200


@dataclass(frozen=True, slots=True)
class TrendsConfig:
    hackernews: HackerNewsConfig | None = None
    reddit: RedditConfig | None = None


@dataclass(frozen=True, slots=True)
class SummarizerConfig:
    provider: str
    model: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryConfig:
    telegram: bool = False


@dataclass(frozen=True, slots=True)
class DiscoverConfig:
    enabled: bool = False
    min_sightings: int = 3


@dataclass(frozen=True, slots=True)
class Config:
    interests: tuple[str, ...]
    follow: tuple[FollowSource, ...]
    trends: TrendsConfig
    summarizer: SummarizerConfig
    delivery: DeliveryConfig
    discover: DiscoverConfig


def resolve_config_path(explicit_path: Path | None = None) -> Path:
    """Resolve the config path from an argument, then the env var, then the default."""
    if explicit_path is not None:
        return explicit_path
    from_env = os.environ.get(CONFIG_PATH_ENV_VAR)
    if from_env:
        return Path(from_env)
    return DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> Config:
    """Read, parse, and validate the configuration file.

    Raises:
        ConfigError: if the file is missing, unparseable, not a mapping, or is
            missing/malformed keys.
    """
    config_path = resolve_config_path(path)
    if not config_path.is_file():
        raise ConfigError(
            f"Configuration file not found at '{config_path}'. "
            f"Set {CONFIG_PATH_ENV_VAR} or create the file."
        )
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"Could not parse YAML in '{config_path}': {error}") from error

    if not isinstance(raw, dict):
        raise ConfigError(f"Expected a mapping at the top level of '{config_path}'.")

    return Config(
        interests=_parse_str_list(raw, "interests"),
        follow=_parse_follow(raw),
        trends=_parse_trends(raw),
        summarizer=_parse_summarizer(raw),
        delivery=_parse_delivery(raw),
        discover=_parse_discover(raw),
    )


def _parse_str_list(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"'{key}' must be a list of strings.")
    return tuple(value)


def _parse_follow(raw: dict[str, Any]) -> tuple[FollowSource, ...]:
    entries = raw.get("follow", [])
    if not isinstance(entries, list):
        raise ConfigError("'follow' must be a list of {name, rss} entries.")
    sources: list[FollowSource] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or "name" not in entry or "rss" not in entry:
            raise ConfigError(f"follow[{index}] must have both 'name' and 'rss'.")
        sources.append(FollowSource(name=str(entry["name"]), rss=str(entry["rss"])))
    return tuple(sources)


def _parse_trends(raw: dict[str, Any]) -> TrendsConfig:
    trends = raw.get("trends") or {}
    if not isinstance(trends, dict):
        raise ConfigError("'trends' must be a mapping.")

    hackernews: HackerNewsConfig | None = None
    if "hackernews" in trends:
        section = trends["hackernews"] or {}
        if not isinstance(section, dict):
            raise ConfigError("'trends.hackernews' must be a mapping.")
        hackernews = HackerNewsConfig(min_points=int(section.get("min_points", 150)))

    reddit: RedditConfig | None = None
    if "reddit" in trends:
        section = trends["reddit"] or {}
        if not isinstance(section, dict):
            raise ConfigError("'trends.reddit' must be a mapping.")
        subreddits = section.get("subreddits", [])
        if not isinstance(subreddits, list) or not all(isinstance(s, str) for s in subreddits):
            raise ConfigError("'trends.reddit.subreddits' must be a list of strings.")
        reddit = RedditConfig(
            subreddits=tuple(subreddits),
            min_upvotes=int(section.get("min_upvotes", 200)),
        )

    return TrendsConfig(hackernews=hackernews, reddit=reddit)


def _parse_summarizer(raw: dict[str, Any]) -> SummarizerConfig:
    summarizer = raw.get("summarizer") or {}
    if not isinstance(summarizer, dict):
        raise ConfigError("'summarizer' must be a mapping.")
    provider = os.environ.get(SUMMARIZER_PROVIDER_ENV_VAR) or summarizer.get("provider")
    if provider not in _VALID_PROVIDERS:
        raise ConfigError(f"'summarizer.provider' must be one of {sorted(_VALID_PROVIDERS)}.")
    model = os.environ.get(SUMMARIZER_MODEL_ENV_VAR) or summarizer.get("model")
    if model is not None and not isinstance(model, str):
        raise ConfigError("'summarizer.model' must be a string.")
    return SummarizerConfig(provider=str(provider), model=model)


def _parse_delivery(raw: dict[str, Any]) -> DeliveryConfig:
    delivery = raw.get("delivery") or {}
    if not isinstance(delivery, dict):
        raise ConfigError("'delivery' must be a mapping.")
    return DeliveryConfig(telegram=bool(delivery.get("telegram", False)))


def _parse_discover(raw: dict[str, Any]) -> DiscoverConfig:
    discover = raw.get("discover") or {}
    if not isinstance(discover, dict):
        raise ConfigError("'discover' must be a mapping.")
    return DiscoverConfig(
        enabled=bool(discover.get("enabled", False)),
        min_sightings=int(discover.get("min_sightings", 3)),
    )
