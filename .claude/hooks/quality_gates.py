#!/usr/bin/env python3
"""Stop hook: run the blocking quality gates before a turn can end.

Only the gates that need the whole tree run here; ruff is already handled
per-file. Exiting 2 blocks the turn and returns the output to Claude. The
sentinel records the file set and time of the last passing run, so the ~5s cost
is paid only when a Python source is added, removed, renamed, or edited.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SENTINEL = PROJECT_ROOT / ".claude" / ".quality_gates_ok"
WATCHED_DIRECTORIES = ("src", "tests")
GATES = (
    ("mypy (strict)", ["mypy", "src", "tests"]),
    ("pytest", ["pytest", "-q", "tests"]),
)


def python_sources() -> list[Path]:
    return sorted(
        path
        for directory in WATCHED_DIRECTORIES
        for path in (PROJECT_ROOT / directory).rglob("*.py")
    )


def manifest(sources: list[Path]) -> str:
    return "".join(f"{path.relative_to(PROJECT_ROOT)}\n" for path in sources)


def python_sources_changed(sources: list[Path]) -> bool:
    if not SENTINEL.exists():
        return True
    # A rename or deletion leaves every surviving file older than the sentinel,
    # so the file set is compared as well as the timestamps.
    if SENTINEL.read_text() != manifest(sources):
        return True
    checkpoint = SENTINEL.stat().st_mtime
    return any(path.stat().st_mtime > checkpoint for path in sources)


def run_gate(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["conda", "run", "-n", "personal_brief", *command],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> None:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        sys.exit(0)
    sources = python_sources()
    if not python_sources_changed(sources):
        sys.exit(0)

    for name, command in GATES:
        result = run_gate(command)
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            print(
                f"Quality gate FAILED: {name}\n\n{output}\n\n"
                "Fix this before ending the turn — do not weaken or skip the check.",
                file=sys.stderr,
            )
            sys.exit(2)

    SENTINEL.write_text(manifest(sources))
    sys.exit(0)


if __name__ == "__main__":
    main()
