from __future__ import annotations

import pathlib

import aiosqlite

_SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"

_connection: aiosqlite.Connection | None = None


async def init_db(db_path: str) -> aiosqlite.Connection:
    """Opens (or creates) the sqlite database and applies the schema."""
    global _connection
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(_SCHEMA_PATH.read_text())
    await conn.commit()
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
