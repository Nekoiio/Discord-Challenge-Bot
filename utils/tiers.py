"""
Tiers live entirely as Discord roles (Le t1 / Le t2 / Le t3 / Le t500).
Rank *within* a tier can't live on a Discord role though, so that's tracked
in the players table (players.tier_rank) and this module is also where that
gets read/backfilled/reordered.
"""
from __future__ import annotations

import discord

import database.players as players_db
from config import CFG

# Highest tier first. "t500" is the pool tier (anyone in it can challenge
# anyone else in it) -- everything else is a strict "challenge the tier
# directly above you" ladder. Within any tier, a player may also challenge
# whoever is ranked directly above them for a promotion within the tier.
TIER_ORDER = ["t1", "t2", "t3", "t500"]

TIER_LABELS = {
    "t1": "Le t1",
    "t2": "Le t2",
    "t3": "Le t3",
    "t500": "Le t500",
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


async def get_ordered_tier_members(guild: discord.Guild, tier: str) -> list[tuple[discord.Member, int]]:
    """
    Returns every member currently holding `tier`'s role, sorted by rank
    within that tier (1 = top). Anyone missing a rank (brand new to the
    tier, or never assigned one) is lazily backfilled to the bottom of the
    tier and persisted -- callers never have to special-case "unranked".
    """
    members = get_tier_members(guild, tier)

    ranked: list[tuple[discord.Member, int]] = []
    unranked: list[discord.Member] = []
    for member in members:
        rank = await players_db.get_tier_rank(member.id)
        if rank is None:
            unranked.append(member)
        else:
            ranked.append((member, rank))

    ranked.sort(key=lambda entry: entry[1])

    next_rank = (ranked[-1][1] + 1) if ranked else 1
    for member in unranked:
        await players_db.set_tier_rank(member.id, next_rank)
        ranked.append((member, next_rank))
        next_rank += 1

    return ranked


async def ensure_tier_rank(guild: discord.Guild, member: discord.Member, tier: str | None) -> int | None:
    """Like get_ordered_tier_members, but returns just one member's rank (backfilling if needed)."""
    if tier is None:
        return None
    rank = await players_db.get_tier_rank(member.id)
    if rank is not None:
        return rank
    for m, r in await get_ordered_tier_members(guild, tier):
        if m.id == member.id:
            return r
    return None


async def move_member_to_rank(guild: discord.Guild, member: discord.Member, tier: str, new_position: int) -> int:
    """
    Reorders `member` to `new_position` (1 = top) within `tier`, shifting
    everyone else in that tier to make room. `tier` is passed explicitly
    (rather than re-derived from member.roles) so this is safe to call
    immediately after changing someone's tier role, without depending on
    Discord's role cache having caught up yet. Returns the position actually
    used (clamped to a valid range).
    """
    ordered = await get_ordered_tier_members(guild, tier)
    ordered = [entry for entry in ordered if entry[0].id != member.id]

    new_position = max(1, min(new_position, len(ordered) + 1))
    ordered.insert(new_position - 1, (member, 0))

    for i, (m, _) in enumerate(ordered, start=1):
        await players_db.set_tier_rank(m.id, i)

    return new_position
