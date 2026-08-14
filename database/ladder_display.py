from __future__ import annotations

from dataclasses import dataclass

from database.db import get_db


@dataclass
class LadderDisplay:
    guild_id: str
    channel_id: str
    message_id: str | None


async def get_display(guild_id: str) -> LadderDisplay | None:
    db = get_db()
    cur = await db.execute("SELECT * FROM ladder_display WHERE guild_id = ?", (guild_id,))
    row = await cur.fetchone()
    if not row:
        return None
    return LadderDisplay(guild_id=row["guild_id"], channel_id=row["channel_id"], message_id=row["message_id"])


async def set_display(guild_id: str, channel_id: str, message_id: str | None) -> None:
    db = get_db()
    await db.execute(
        """INSERT INTO ladder_display (guild_id, channel_id, message_id) VALUES (?, ?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id, message_id = excluded.message_id""",
        (guild_id, channel_id, message_id),
    )
    await db.commit()
