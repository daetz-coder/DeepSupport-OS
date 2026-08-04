"""Shared fixtures — isolated temp SQLite DB."""

from __future__ import annotations

import pytest

from deepsupport_os.core.config import get_settings
from deepsupport_os.db.models import reset_engine, init_db
from deepsupport_os.db.seed import seed_database


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    reset_engine()
    init_db()
    seed_database(force=True)
    yield
    reset_engine()
    get_settings.cache_clear()
