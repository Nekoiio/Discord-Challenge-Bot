"""
Content for the auto-updating ladder message. Deliberately plain Discord
markdown (# / ## headers, numbered lists) sent as regular message content --
not an embed -- per request. Mentions use real <@id> syntax so they render
as a proper highlighted "@name" that's clickable, but the actual ping is
suppressed at send/edit time (see services.sync_ladder_display), not here.
"""
from __future__ import annotations

import discord

import database.players as players_db
from utils.tiers import TIER_LABELS, TIER_ORDER,TIER_LIMITS, get_ordered_tier_members

TIER_HEADER_EMOJI = {"t1": "🥇", "t2": "🥈", "t3": "🥉", "t500": "🔰"}

# Discord message content is capped at 2000 characters.
MAX_MESSAGE_LENGTH = 2000


async def build_ladder_markdown(guild: discord.Guild) -> str:
    lines = ["# LeComp Roster (In order)", ""]

    for tier in TIER_ORDER:
        if tier == "t500":
            continue  # t500 is the pool tier, not a ranked tier, so we don't show it here
        ordered = await get_ordered_tier_members(guild, tier)

        if TIER_LIMITS[tier] == "NONE":
            lines.append(f"## {TIER_LABELS[tier]} | {len(ordered)}/∞")
        else:
            lines.append(f"## {TIER_LABELS[tier]} | {len(ordered)}/{TIER_LIMITS[tier]}")

        if ordered:
            for member, rank in ordered:
                jersey = await players_db.get_jersey_number(member.id)
                jersey_str = f" — #{jersey}" if jersey is not None else ""
                lines.append(f"{rank}. {member.mention}{jersey_str}")
        else:
            lines.append("*empty*")
        lines.append("")

    timestamp = discord.utils.format_dt(discord.utils.utcnow(), style="R")
    lines.append(f"-# Last updated {timestamp}")

    content = "\n".join(lines).strip()
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[: MAX_MESSAGE_LENGTH - 20].rstrip() + "\n...*(truncated)*"
    return content
