#!/usr/bin/env python3
"""PostToolUse/Write|Edit hook: format and autofix a just-written Python file.

Formatting runs per-file here rather than in the Stop hook so the blocking gate
only ever reports problems that need a human decision.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORMATTED_DIRECTORIES = ("src", "tests")


def target_file(payload: dict[str, object]) -> Path | None:
    tool_input = payload.get("tool_input")
    tool_response = payload.get("tool_response")
    raw = None
    if isinstance(tool_response, dict):
        raw = tool_response.get("filePath")
    if not raw and isinstance(tool_input, dict):
        raw = tool_input.get("file_path")
    if not isinstance(raw, str):
        return None

    path = Path(raw)
    if path.suffix != ".py":
        return None
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return None
    if relative.parts[0] not in FORMATTED_DIRECTORIES:
        return None
    return path


def main() -> None:
    path = target_file(json.load(sys.stdin))
    if path is None:
        sys.exit(0)

    quoted = str(path)
    subprocess.run(
        [
            "conda",
            "run",
            "-n",
            "personal_brief",
            "bash",
            "-c",
            f'ruff format "{quoted}" && ruff check --fix "{quoted}"',
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
