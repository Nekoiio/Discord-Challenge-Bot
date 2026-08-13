from __future__ import annotations

import discord

from config import CFG


def is_supervisor(member: discord.Member) -> bool:
    return any(role.id == CFG.supervisor_role_id for role in member.roles)
