from __future__ import annotations

from datetime import datetime

from database.db import get_db


async def _upsert_field(discord_id: str, column: str, value) -> None:
    db = get_db()
    await db.execute(
        f"""INSERT INTO players (discord_id, {column}) VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET {column} = excluded.{column}""",
        (discord_id, value),
    )
    await db.commit()


async def get_cooldown(discord_id: int | str) -> datetime | None:
    db = get_db()
    cur = await db.execute(
        "SELECT cooldown_until FROM players WHERE discord_id = ?", (str(discord_id),)
    )
    row = await cur.fetchone()
    if row and row["cooldown_until"]:
        return datetime.fromisoformat(row["cooldown_until"])
    return None


async def set_cooldown(discord_id: int | str, cooldown_until: datetime | None) -> None:
    await _upsert_field(
        str(discord_id), "cooldown_until", cooldown_until.isoformat() if cooldown_until else None
    )


async def clear_cooldown(discord_id: int | str) -> None:
    await set_cooldown(discord_id, None)


async def get_tier_rank(discord_id: int | str) -> int | None:
    """A player's rank within whatever tier they're currently in (1 = top). None if never assigned."""
    db = get_db()
    cur = await db.execute(
        "SELECT tier_rank FROM players WHERE discord_id = ?", (str(discord_id),)
    )
    row = await cur.fetchone()
    if row and row["tier_rank"] is not None:
        return row["tier_rank"]
    return None


async def set_tier_rank(discord_id: int | str, rank: int | None) -> None:
    await _upsert_field(str(discord_id), "tier_rank", rank)


async def get_jersey_number(discord_id: int | str) -> int | None:
    db = get_db()
    cur = await db.execute(
        "SELECT jersey_number FROM players WHERE discord_id = ?", (str(discord_id),)
    )
    row = await cur.fetchone()
    if row and row["jersey_number"] is not None:
        return row["jersey_number"]
    return None


async def set_jersey_number(discord_id: int | str, jersey_number: int | None) -> None:
    await _upsert_field(str(discord_id), "jersey_number", jersey_number)
