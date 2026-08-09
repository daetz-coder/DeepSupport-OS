"""Additive migration tests: legacy DBs gain columns added after first deploy."""

from __future__ import annotations

import sqlite3

from deepsupport_os.core.config import get_settings
from deepsupport_os.db.migrate import migrate_db
from deepsupport_os.db.models import init_db, reset_engine


def _legacy_db(path):
    """Create a pre-R2 schema (audit_logs / tickets missing the new columns)."""
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE audit_logs ("
        "id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, tool TEXT NOT NULL, "
        "arguments TEXT, result TEXT, timestamp DATETIME)"
    )
    con.execute(
        "CREATE TABLE tickets ("
        "ticket_id TEXT PRIMARY KEY, employee_id TEXT, category TEXT, priority TEXT, "
        "status TEXT, assignee TEXT, title TEXT, description TEXT, resolution TEXT, "
        "created_at DATETIME, updated_at DATETIME)"
    )
    con.commit()
    con.close()


def _cols(path, table):
    con = sqlite3.connect(str(path))
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    con.close()
    return cols


def _indexes(path, table):
    con = sqlite3.connect(str(path))
    idx = {r[1] for r in con.execute(f"PRAGMA index_list({table})")}
    con.close()
    return idx


def _make_env(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db(db_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    reset_engine()
    return db_path


def test_init_db_migrates_legacy_schema(tmp_path, monkeypatch):
    db_path = _make_env(tmp_path, monkeypatch)
    init_db()

    assert "thread_id" in _cols(db_path, "audit_logs")
    assert "idempotency_key" in _cols(db_path, "tickets")
    # applied_actions is a brand-new table — created by create_all, not ADD COLUMN.
    con = sqlite3.connect(str(db_path))
    has_ledger = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='applied_actions'"
    ).fetchone()
    con.close()
    assert has_ledger

    # Existing seeded data is preserved (columns are added, rows untouched).
    con = sqlite3.connect(str(db_path))
    con.execute("INSERT INTO tickets (ticket_id, title, description) VALUES ('T1','x','y')")
    con.commit()
    row = con.execute("SELECT ticket_id, idempotency_key FROM tickets WHERE ticket_id='T1'").fetchone()
    con.close()
    assert row == ("T1", None)
    reset_engine()
    get_settings.cache_clear()


def test_migrate_recreates_unique_index_for_added_column(tmp_path, monkeypatch):
    db_path = _make_env(tmp_path, monkeypatch)
    init_db()
    idx = _indexes(db_path, "tickets")
    assert "ix_tickets_idempotency_key" in idx
    # Unique index actually enforces dedup on the migrated column.
    con = sqlite3.connect(str(db_path))
    con.execute("INSERT INTO tickets (ticket_id, title, description) VALUES ('T1','a','b')")
    con.commit()
    try:
        con.execute(
            "INSERT INTO tickets (ticket_id, title, description, idempotency_key) "
            "VALUES ('T2','c','d','k')"
        )
        con.commit()
        with con:  # duplicate key → IntegrityError
            con.execute(
                "INSERT INTO tickets (ticket_id, title, description, idempotency_key) "
                "VALUES ('T3','e','f','k')"
            )
        raise AssertionError("duplicate idempotency_key should have been rejected")
    except sqlite3.IntegrityError:
        pass
    finally:
        con.close()
    reset_engine()
    get_settings.cache_clear()


def test_migrate_adds_not_null_column_with_default(tmp_path, monkeypatch):
    """NOT NULL columns with a scalar model default migrate via ADD COLUMN."""
    db_path = tmp_path / "legacy.db"
    con = sqlite3.connect(str(db_path))
    con.execute(
        "CREATE TABLE eval_runs ("
        "run_id TEXT PRIMARY KEY, mode TEXT NOT NULL, cases_path TEXT, "
        "total INTEGER, passed INTEGER, failed INTEGER)"
    )
    con.execute("INSERT INTO eval_runs (run_id, mode) VALUES ('r1', 'offline')")
    con.commit()
    con.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    reset_engine()
    try:
        init_db()

        # use_daytona is Boolean NOT NULL default=False on the model — previously
        # skipped, now added with a constant default.
        cols = _cols(db_path, "eval_runs")
        assert "use_daytona" in cols
        con = sqlite3.connect(str(db_path))
        row = con.execute("SELECT use_daytona FROM eval_runs WHERE run_id='r1'").fetchone()
        con.close()
        assert row == (0,)
    finally:
        reset_engine()
        get_settings.cache_clear()


def test_migrate_is_idempotent(tmp_path, monkeypatch):
    db_path = _make_env(tmp_path, monkeypatch)
    init_db()  # init_db already runs migrate_db internally
    # Explicit repeat runs are no-ops — nothing left to apply.
    assert migrate_db() == []
    assert migrate_db() == []
    reset_engine()
    get_settings.cache_clear()
