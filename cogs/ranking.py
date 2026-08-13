from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database.players as players_db
from ui.embeds import ladder_embed
from utils.tiers import TIER_LABELS, get_member_tier


class Ranking(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ladder", description="Show the current ladder rankings by tier.")
    async def ladder(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=ladder_embed(interaction.guild))

    @app_commands.command(name="rank", description="Show a player's current tier.")
    @app_commands.describe(member="The player to look up (defaults to you).")
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        tier = get_member_tier(member)
        if not tier:
            await interaction.response.send_message(
                f"{member.mention} doesn't have a tier role yet.", ephemeral=True
            )
            return

        cooldown_until = await players_db.get_cooldown(member.id)
        cooldown_note = ""
        if cooldown_until:
            cooldown_note = f" (on cooldown until {discord.utils.format_dt(cooldown_until)})"
        await interaction.response.send_message(
            f"{member.mention} is currently in **{TIER_LABELS[tier]}**{cooldown_note}."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Ranking(bot))
