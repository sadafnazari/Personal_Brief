from __future__ import annotations

import os
from pathlib import Path

import pytest

from personal_brief.env import load_dotenv


def test_load_dotenv_sets_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PB_TEST_VAR", raising=False)
    monkeypatch.delenv("QUOTED_VAR", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n\nPB_TEST_VAR=hello\nQUOTED_VAR='quoted value'\n",
        encoding="utf-8",
    )

    load_dotenv(env_file)

    assert os.environ["PB_TEST_VAR"] == "hello"
    assert os.environ["QUOTED_VAR"] == "quoted value"


def test_load_dotenv_does_not_override_existing_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PB_TEST_VAR", "already-set")

    env_file = tmp_path / ".env"
    env_file.write_text("PB_TEST_VAR=from-dotenv\n", encoding="utf-8")

    load_dotenv(env_file)

    assert os.environ["PB_TEST_VAR"] == "already-set"


def test_load_dotenv_missing_file_is_a_no_op(tmp_path: Path) -> None:
    load_dotenv(tmp_path / "does-not-exist.env")
