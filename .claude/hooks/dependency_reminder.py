#!/usr/bin/env python3
"""PostToolUse/Write|Edit hook: flag dependency changes to pyproject.toml.

An editable install picks up code changes automatically but not new
dependencies, so every `[project.dependencies]` edit needs a reinstall.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REMINDER = (
    "pyproject.toml changed. If you added or changed a dependency: say so "
    'explicitly in your response, and remind the user to re-run `pip install -e ".[dev]"` '
    "in the personal_brief conda env — the editable install will not pick it up on its own."
)


def main() -> None:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input")
    raw = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or Path(raw).name != "pyproject.toml":
        sys.exit(0)

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": REMINDER,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
