"""Keep tests off the developer's real ~/.llmbench/config.yaml."""

from __future__ import annotations

import pytest

from llmbench import config


@pytest.fixture(autouse=True)
def _isolate_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.yaml")
