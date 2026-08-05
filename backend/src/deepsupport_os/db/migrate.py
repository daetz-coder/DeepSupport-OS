"""Additive schema migration for legacy SQLite databases.

``Base.metadata.create_all`` creates missing *tables* but never adds missing
*columns* to existing tables. Columns introduced after the first deployment
(R2-1 / R2-2 / R2-5) therefore do not appear on an existing ``deepsupport.db``:

- ``audit_logs.thread_id``      (R2-5 — audit scoped to thread)
- ``tickets.idempotency_key``   (R2-2 — create_ticket exactly-once)
- ``applied_actions`` table     (R2-1 — ledger; a new table, covered by create_all)

``migrate_db`` runs after ``create_all`` and adds any *nullable* model column
missing from an existing table, recreating the secondary / unique index that
SQLite's ``ADD COLUMN`` cannot attach. Non-nullable additions are skipped with
a warning: SQLite can only ``ADD COLUMN`` with a constant default, so those
require a full table rebuild (out of scope for the current mock DB).
"""

from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def migrate_db() -> list[str]:
    """Add missing model columns to existing tables; return ``table.column`` labels."""
    from deepsupport_os.db.models import Base, get_engine

    engine = get_engine()
    applied: list[str] = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table.name})"))
            }
            for column in table.columns:
                if column.name in existing:
                    continue
                if column.nullable is not True:
                    logger.warning(
                        "migrate skip %s.%s: NOT NULL without constant default — needs table rebuild",
                        table.name,
                        column.name,
                    )
                    continue
                conn.execute(
                    text(f"ALTER TABLE {table.name} ADD COLUMN {_column_ddl(engine, column)}")
                )
                applied.append(f"{table.name}.{column.name}")
                _recreate_indexes(conn, table.name, column)
    if applied:
        logger.info("schema migration applied: %s", ", ".join(applied))
    return applied


def _column_ddl(engine, column) -> str:
    """SQLite-compatible ``name TYPE [NOT NULL DEFAULT ...]`` for one column."""
    col_type = column.type.compile(engine.dialect)
    ddl = f"{column.name} {col_type}"
    if column.nullable is False and column.server_default is not None:
        ddl += f" NOT NULL DEFAULT {column.server_default.arg}"
    return ddl


def _recreate_indexes(conn, table_name: str, column) -> None:
    """Recreate unique / secondary indexes that ADD COLUMN cannot attach."""
    unique = bool(getattr(column, "unique", False))
    indexed = unique or bool(getattr(column, "index", False))
    if not indexed:
        return
    idx_name = f"ix_{table_name}_{column.name}"
    existing = {row[1] for row in conn.execute(text(f"PRAGMA index_list({table_name})"))}
    if idx_name in existing:
        return
    kind = "UNIQUE INDEX" if unique else "INDEX"
    conn.execute(text(f"CREATE {kind} IF NOT EXISTS {idx_name} ON {table_name} ({column.name})"))
