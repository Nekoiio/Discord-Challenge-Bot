from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database.players as players_db
from ui.embeds import ladder_embed
from utils.tiers import TIER_LABELS, ensure_tier_rank, get_member_tier


class Ranking(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ladder", description="Show the current ladder rankings by tier.")
    async def ladder(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await ladder_embed(interaction.guild))

    @app_commands.command(name="rank", description="Show a player's current tier and rank.")
    @app_commands.describe(member="The player to look up (defaults to you).")
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        tier = get_member_tier(member)
        if not tier:
            await interaction.response.send_message(
                f"{member.mention} doesn't have a tier role yet.", ephemeral=True
            )
            return

        tier_rank = await ensure_tier_rank(interaction.guild, member, tier)
        jersey = await players_db.get_jersey_number(member.id)
        cooldown_until = await players_db.get_cooldown(member.id)

        jersey_note = f" (Jersey #{jersey})" if jersey is not None else ""
        cooldown_note = ""
        if cooldown_until:
            cooldown_note = f" — on cooldown until {discord.utils.format_dt(cooldown_until)}"

        await interaction.response.send_message(
            f"{member.mention} is rank **#{tier_rank}** in **{TIER_LABELS[tier]}**{jersey_note}{cooldown_note}."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Ranking(bot))
