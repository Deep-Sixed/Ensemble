from __future__ import annotations

from pathlib import Path

import pytest

from ensemble.config import load_config, load_env_file


def test_env_file_loads_without_overriding_existing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "export ENSEMBLE_WORKSPACE='/tmp/from-file'\n"
        'ENSEMBLE_MAX_FILE_BYTES="1234"\n'
        "not a setting\n",
        encoding="utf-8",
    )
    # setenv first so monkeypatch restores the variable after load_env_file sets it.
    monkeypatch.setenv("ENSEMBLE_WORKSPACE", "placeholder")
    monkeypatch.delenv("ENSEMBLE_WORKSPACE")
    monkeypatch.setenv("ENSEMBLE_MAX_FILE_BYTES", "999")

    config = load_config(env)

    assert config.workspace == Path("/tmp/from-file")
    assert config.max_file_bytes == 999


def test_missing_env_file_is_ignored(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "missing.env") is False
