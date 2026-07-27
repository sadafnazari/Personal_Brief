"""Minimal ``.env`` loader.

A hand-rolled ~15 lines instead of a dependency (``python-dotenv``) for
something this small — see ``CLAUDE.md`` on when a dependency is warranted.
Only sets variables that aren't already in the environment, so a real
exported env var always wins over ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DOTENV_PATH = Path(".env")


def load_dotenv(path: Path = DEFAULT_DOTENV_PATH) -> None:
    """Load ``KEY=VALUE`` lines from ``path`` into ``os.environ``, if it exists."""
    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
