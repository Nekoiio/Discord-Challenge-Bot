"""
Content for the auto-updating ladder message. Deliberately plain Discord
markdown (# / ## headers, bullet lists) sent as regular message content --
not an embed -- per request.
"""
from __future__ import annotations

import discord

from utils.tiers import TIER_LABELS, TIER_ORDER, get_tier_members

TIER_HEADER_EMOJI = {"t1": "🥇", "t2": "🥈", "t3": "🥉", "t500": "🔰"}

# Discord message content is capped at 2000 characters.
MAX_MESSAGE_LENGTH = 2000


def build_ladder_markdown(guild: discord.Guild) -> str:
    lines = ["# 🏆 Ladder Rankings", ""]

    for tier in TIER_ORDER:
        members = get_tier_members(guild, tier)
        lines.append(f"## {TIER_HEADER_EMOJI[tier]} {TIER_LABELS[tier]}")
        if members:
            lines.extend(f"- {m.mention}" for m in members)
        else:
            lines.append("*empty*")
        lines.append("")

    timestamp = discord.utils.format_dt(discord.utils.utcnow(), style="R")
    lines.append(f"-# Last updated {timestamp}")

    content = "\n".join(lines).strip()
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[: MAX_MESSAGE_LENGTH - 20].rstrip() + "\n...*(truncated)*"
    return content
