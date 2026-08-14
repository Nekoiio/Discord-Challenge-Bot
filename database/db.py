from __future__ import annotations

import pathlib

import aiosqlite

_SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"

_connection: aiosqlite.Connection | None = None

# CREATE TABLE IF NOT EXISTS silently skips tables that already exist, so any
# column added to schema.sql after the table was first created never shows up
# in an existing database file. Listing added columns here lets us patch
# already-existing databases in place instead of requiring a manual DB wipe
# every time the schema changes. Safe to re-run -- duplicate-column errors are
# swallowed.
_COLUMN_MIGRATIONS = [
    ("challenges", "match_message_id", "TEXT"),
    ("players", "tier_rank", "INTEGER"),
    ("players", "jersey_number", "INTEGER"),
]


async def _apply_column_migrations(conn: aiosqlite.Connection) -> None:
    for table, column, col_type in _COLUMN_MIGRATIONS:
        try:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    await conn.commit()


async def init_db(db_path: str) -> aiosqlite.Connection:
    """Opens (or creates) the sqlite database, applies the schema, and patches in any new columns."""
    global _connection
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(_SCHEMA_PATH.read_text())
    await conn.commit()
    await _apply_column_migrations(conn)
    _connection = conn
    return conn


def get_db() -> aiosqlite.Connection:
    if _connection is None:
        raise RuntimeError("Database not initialized yet — call init_db() first.")
    return _connection


async def close_db() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
