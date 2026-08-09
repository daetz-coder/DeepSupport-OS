"""Checkpointer concurrency hardening regression tests."""

import sqlite3


def _reset_globals(saved):
    from deepsupport_os.harness import agent as ag

    ag._checkpointer, ag._sqlite_conn = saved


def test_get_checkpointer_enables_wal_and_busy_timeout(tmp_path, monkeypatch):
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.harness import agent as ag

    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite:///{str(tmp_path).replace(chr(92), '/')}/db.sqlite"
    )
    settings = get_settings()
    # Re-home root so the checkpointer lands under tmp_path and does not touch
    # the real data/checkpoints.sqlite used by other tests.
    settings.root_dir = tmp_path
    (settings.resolve("data")).mkdir(parents=True, exist_ok=True)

    saved = (ag._checkpointer, ag._sqlite_conn)
    try:
        ag._checkpointer = None
        ag._sqlite_conn = None
        cp = ag.get_checkpointer()
        assert cp is not None

        db = settings.resolve("data/checkpoints.sqlite")
        # journal_mode is a persistent DB property; busy_timeout is per-connection,
        # so verify the shared connection that the saver actually uses.
        conn = sqlite3.connect(str(db))
        journal = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        conn.close()
        busy = int(ag._sqlite_conn.execute("PRAGMA busy_timeout").fetchone()[0])

        assert journal == "wal"
        assert busy >= 30000
    finally:
        get_settings.cache_clear()
        _reset_globals(saved)