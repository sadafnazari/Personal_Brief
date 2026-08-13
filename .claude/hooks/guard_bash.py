#!/usr/bin/env python3
"""PreToolUse/Bash hook: enforce the conda env and guard git history rewrites."""

from __future__ import annotations

import json
import re
import shlex
import sys

CONDA_ENV = "personal_brief"
CONDA_PREFIX = f"conda run -n {CONDA_ENV}"

# Tools that must run inside the project env so they see the editable install.
ENV_BOUND_COMMANDS = frozenset({"pytest", "mypy", "ruff", "pip", "pip3", "personal-brief"})

SEGMENT_SEPARATORS = re.compile(r"(?:\|\||&&|[;|&])")


def emit(decision: str, reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def leading_words(command: str) -> list[list[str]]:
    """Split a shell line into segments and return each segment's tokens."""
    segments = []
    for segment in SEGMENT_SEPARATORS.split(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:  # unbalanced quotes — let the real shell complain
            continue
        if tokens:
            segments.append(tokens)
    return segments


def bare_env_bound_tool(segments: list[list[str]]) -> str | None:
    """Return the first env-bound tool invoked outside `conda run`, if any."""
    for tokens in segments:
        if tokens[0] == "conda":
            continue
        # `VAR=1 pytest ...` — skip leading env-var assignments.
        index = 0
        while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
            index += 1
        if index >= len(tokens):
            continue
        program = tokens[index].rsplit("/", 1)[-1]
        if program in ENV_BOUND_COMMANDS:
            return program
        if program in {"python", "python3"} and tokens[index + 1 : index + 2] == ["-m"]:
            module = tokens[index + 2] if len(tokens) > index + 2 else ""
            if module in ENV_BOUND_COMMANDS:
                return module
    return None


def main() -> None:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    command = payload.get("tool_input", {}).get("command", "")
    segments = leading_words(command)

    if "Co-Authored-By" in command and "git" in command:
        emit(
            "deny",
            "This repo does not list Claude as a commit co-author. Drop the "
            "Co-Authored-By trailer and commit again.",
        )

    tool = bare_env_bound_tool(segments)
    if tool is not None:
        emit(
            "deny",
            f"`{tool}` must run inside the project env, which holds the editable "
            f"install. Re-run it as: {CONDA_PREFIX} {tool} ...",
        )

    for tokens in segments:
        if tokens[:1] != ["git"]:
            continue
        subcommand = tokens[1] if len(tokens) > 1 else ""
        if subcommand == "push" and {"-f", "--force"} & set(tokens):
            emit(
                "ask",
                "Force-push rewrites published history — confirm this is what you want.",
            )
        if subcommand in {"commit", "push"}:
            emit(
                "ask",
                f"`git {subcommand}` only runs when you explicitly ask for it. "
                "Confirm if you requested this.",
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
