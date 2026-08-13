"""
This module is the only place that
translates between "a discord.Member" and "which tier they're in."
"""
from __future__ import annotations

import discord

from config import CFG

# Highest tier first. "t500" is the pool tier (anyone in it can challenge
# anyone else in it) -- everything else is a strict "challenge the tier
# directly above you" ladder.
TIER_ORDER = ["t1", "t2", "t3", "t500"]

TIER_LABELS = {
    "t1": "t1",
    "t2": "t2",
    "t3": "t3",
    "t500": "t500",
}


def get_member_tier(member: discord.Member) -> str | None:
    """Returns 't1'/'t2'/'t3'/'t500', or None if they hold none of those roles."""
    member_role_ids = {r.id for r in member.roles}
    for tier_name in TIER_ORDER:
        role_id = CFG.tier_role_ids.get(tier_name)
        if role_id and role_id in member_role_ids:
            return tier_name
    return None


async def set_member_tier(member: discord.Member, new_tier: str) -> None:
    """Removes any other tier role the member has and applies new_tier's role."""
    guild = member.guild
    new_role_id = CFG.tier_role_ids[new_tier]
    new_role = guild.get_role(new_role_id)

    roles_to_remove = [
        guild.get_role(role_id)
        for tier_name, role_id in CFG.tier_role_ids.items()
        if tier_name != new_tier
    ]
    roles_to_remove = [r for r in roles_to_remove if r and r in member.roles]

    if roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason="Ladder tier updated")
    if new_role and new_role not in member.roles:
        await member.add_roles(new_role, reason="Ladder tier updated")


def get_tier_members(guild: discord.Guild, tier: str) -> list[discord.Member]:
    role = guild.get_role(CFG.tier_role_ids[tier])
    return list(role.members) if role else []
