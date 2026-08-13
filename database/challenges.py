from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from database.db import get_db


@dataclass
class Challenge:
    id: int
    guild_id: str
    channel_id: str
    challenger_id: str
    challenged_id: str
    status: str
    created_at: datetime
    responded_at: datetime | None
    server_agreed: str | None
    supervisor_id: str | None
    thread_id: str | None
    match_message_id: str | None
    tracker_message_id: str | None
    request_message_id: str | None
    supervisor_message_id: str | None
    current_game: int
    p1_points: int
    p2_points: int
    game_scores: list[tuple[int, int]] = field(default_factory=list)
    winner_id: str | None = None

    @staticmethod
    def from_row(row) -> "Challenge":
        return Challenge(
            id=row["id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            challenger_id=row["challenger_id"],
            challenged_id=row["challenged_id"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            responded_at=(
                datetime.fromisoformat(row["responded_at"])
                if row["responded_at"]
                else None
            ),
            server_agreed=row["server_agreed"],
            supervisor_id=row["supervisor_id"],
            thread_id=row["thread_id"],
            match_message_id=row["match_message_id"],
            tracker_message_id=row["tracker_message_id"],
            request_message_id=row["request_message_id"],
            supervisor_message_id=row["supervisor_message_id"],
            current_game=row["current_game"],
            p1_points=row["p1_points"],
            p2_points=row["p2_points"],
            game_scores=[tuple(g) for g in json.loads(row["game_scores"])],
            winner_id=row["winner_id"],
        )


async def create_challenge(
    *, guild_id: str, channel_id: str, challenger_id: str, challenged_id: str
) -> Challenge:
    db = get_db()
    now = datetime.now().isoformat()
    cur = await db.execute(
        """INSERT INTO challenges
           (guild_id, channel_id, challenger_id, challenged_id, status, created_at)
           VALUES (?, ?, ?, ?, 'pending', ?)""",
        (guild_id, channel_id, challenger_id, challenged_id, now),
    )
    await db.commit()
    return await get_challenge(cur.lastrowid)


async def get_challenge(challenge_id: int) -> Challenge | None:
    db = get_db()
    cur = await db.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,))
    row = await cur.fetchone()
    return Challenge.from_row(row) if row else None


async def get_active_challenge_for(discord_id: str) -> Challenge | None:
    """Any challenge involving this player that isn't finished yet."""
    db = get_db()
    cur = await db.execute(
        """SELECT * FROM challenges
           WHERE (challenger_id = ? OR challenged_id = ?)
             AND status IN ('pending', 'accepted', 'in_progress')""",
        (discord_id, discord_id),
    )
    row = await cur.fetchone()
    return Challenge.from_row(row) if row else None


async def get_stale_pending(older_than: datetime) -> list[Challenge]:
    db = get_db()
    cur = await db.execute(
        "SELECT * FROM challenges WHERE status = 'pending' AND created_at < ?",
        (older_than.isoformat(),),
    )
    rows = await cur.fetchall()
    return [Challenge.from_row(r) for r in rows]


async def get_in_progress() -> list[Challenge]:
    db = get_db()
    cur = await db.execute(
        "SELECT * FROM challenges WHERE status IN ('accepted', 'in_progress')"
    )
    rows = await cur.fetchall()
    return [Challenge.from_row(r) for r in rows]


async def update_status(challenge_id: int, status: str, responded_at: datetime | None = None) -> None:
    db = get_db()
    if responded_at:
        await db.execute(
            "UPDATE challenges SET status = ?, responded_at = ? WHERE id = ?",
            (status, responded_at.isoformat(), challenge_id),
        )
    else:
        await db.execute(
            "UPDATE challenges SET status = ? WHERE id = ?", (status, challenge_id)
        )
    await db.commit()


async def set_message_refs(
    challenge_id: int,
    *,
    request_message_id: str | None = None,
    supervisor_message_id: str | None = None,
    tracker_message_id: str | None = None,
    thread_id: str | None = None,
    match_message_id: str | None = None,
) -> None:
    db = get_db()
    fields, values = [], []
    for col, val in (
        ("request_message_id", request_message_id),
        ("supervisor_message_id", supervisor_message_id),
        ("tracker_message_id", tracker_message_id),
        ("thread_id", thread_id),
        ("match_message_id", match_message_id),
    ):
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)
    if not fields:
        return
    values.append(challenge_id)
    await db.execute(f"UPDATE challenges SET {', '.join(fields)} WHERE id = ?", values)
    await db.commit()


async def set_supervisor(challenge_id: int, supervisor_id: str) -> None:
    db = get_db()
    await db.execute(
        "UPDATE challenges SET supervisor_id = ? WHERE id = ?",
        (supervisor_id, challenge_id),
    )
    await db.commit()


async def set_server_agreed(challenge_id: int, server: str) -> None:
    db = get_db()
    await db.execute(
        "UPDATE challenges SET server_agreed = ? WHERE id = ?", (server, challenge_id)
    )
    await db.commit()


async def add_point(challenge_id: int, side: str, amount: int = 1) -> Challenge:
    """side is 'p1' (challenger) or 'p2' (challenged)."""
    db = get_db()
    col = "p1_points" if side == "p1" else "p2_points"
    await db.execute(
        f"UPDATE challenges SET {col} = {col} + ? WHERE id = ?", (amount, challenge_id)
    )
    await db.commit()
    return await get_challenge(challenge_id)


async def undo_point(challenge_id: int, side: str) -> Challenge:
    db = get_db()
    col = "p1_points" if side == "p1" else "p2_points"
    await db.execute(
        f"UPDATE challenges SET {col} = MAX({col} - 1, 0) WHERE id = ?",
        (challenge_id,),
    )
    await db.commit()
    return await get_challenge(challenge_id)


async def finalize_current_game(challenge_id: int) -> Challenge:
    """Pushes current p1/p2 points into game_scores, resets for next game."""
    challenge = await get_challenge(challenge_id)
    scores = challenge.game_scores + [(challenge.p1_points, challenge.p2_points)]
    db = get_db()
    await db.execute(
        """UPDATE challenges
           SET game_scores = ?, p1_points = 0, p2_points = 0, current_game = current_game + 1
           WHERE id = ?""",
        (json.dumps(scores), challenge_id),
    )
    await db.commit()
    return await get_challenge(challenge_id)


async def set_winner(challenge_id: int, winner_id: str) -> None:
    db = get_db()
    await db.execute(
        "UPDATE challenges SET winner_id = ?, status = 'complete' WHERE id = ?",
        (winner_id, challenge_id),
    )
    await db.commit()
