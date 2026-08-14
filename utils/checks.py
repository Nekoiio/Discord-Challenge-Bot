from __future__ import annotations

import discord

from config import CFG


def is_supervisor(member: discord.Member) -> bool:
    return any(role.id == CFG.supervisor_role_id for role in member.roles)


def is_admin(member: discord.Member) -> bool:
    """Gates the ranking-management commands (/setrank, /setjersey). Uses Discord's
    built-in Administrator permission rather than a separately-configured role."""
    return member.guild_permissions.administrator
