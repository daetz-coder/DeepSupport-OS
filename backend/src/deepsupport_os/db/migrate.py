"""Additive schema migration for legacy SQLite databases.

``Base.metadata.create_all`` creates missing *tables* but never adds missing
*columns* to existing tables. Columns introduced after the first deployment
(R2-1 / R2-2 / R2-5) therefore do not appear on an existing ``deepsupport.db``:

- ``audit_logs.thread_id``      (R2-5 — audit scoped to thread)
- ``tickets.idempotency_key``   (R2-2 — create_ticket exactly-once)
- ``applied_actions`` table     (R2-1 — ledger; a new table, covered by create_all)

``migrate_db`` runs after ``create_all`` and adds any *nullable* model column
missing from an existing table, recreating the secondary / unique index that
SQLite's ``ADD COLUMN`` cannot attach. NOT NULL additions are allowed only when
a constant default exists (a model ``server_default`` or a scalar ``column.default``);
otherwise they are skipped with a warning, since SQLite can only ``ADD COLUMN``
with a constant default and those would require a full table rebuild.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.sql.expression import literal

logger = logging.getLogger(__name__)


def _constant_default_sql(engine, column) -> str | None:
    """Constant SQL literal usable in ``ADD COLUMN ... DEFAULT``, or None.

    Prefers the model's ``server_default``; falls back to a scalar
    ``column.default`` (e.g. ``default=True`` → ``NOT NULL DEFAULT 1``).
    Callables (e.g. ``default=datetime.now``) and clause defaults are treated
    as non-constant and skipped.
    """
    if column.server_default is not None:
        return str(column.server_default.arg)
    d = getattr(column, "default", None)
    if d is None:
        return None
    arg = getattr(d, "arg", None)
    if arg is None or callable(arg):
        return None
    try:
        return literal(arg).compile(
            dialect=engine.dialect,
            compile_kwargs={"literal_binds": True},
        ).string
    except Exception:  # noqa: BLE001 - unrenderable literal → treat as unavailable
        return None


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
                if column.nullable is not True and _constant_default_sql(engine, column) is None:
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
    if column.nullable is False:
        default = _constant_default_sql(engine, column)
        if default is not None:
            ddl += f" NOT NULL DEFAULT {default}"
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
