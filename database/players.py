from __future__ import annotations

from datetime import datetime

from database.db import get_db


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
    db = get_db()
    await db.execute(
        """INSERT INTO players (discord_id, cooldown_until) VALUES (?, ?)
           ON CONFLICT(discord_id) DO UPDATE SET cooldown_until = excluded.cooldown_until""",
        (str(discord_id), cooldown_until.isoformat() if cooldown_until else None),
    )
    await db.commit()


async def clear_cooldown(discord_id: int | str) -> None:
    await set_cooldown(discord_id, None)
