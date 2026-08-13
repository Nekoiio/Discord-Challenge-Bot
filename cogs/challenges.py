from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database.challenges as challenges_db
import database.players as players_db
from ui.embeds import challenge_request_embed
from ui.views import ChallengeResponseView
from utils.ladder_logic import can_challenge
from utils.tiers import get_member_tier


class Challenges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="challenge", description="Challenge the player above you on the ladder.")
    @app_commands.describe(opponent="The player you want to challenge.")
    async def challenge(self, interaction: discord.Interaction, opponent: discord.Member):
        challenger = interaction.user

        if opponent.id == challenger.id:
            await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
            return

        challenger_tier = get_member_tier(challenger)
        challenged_tier = get_member_tier(opponent)

        if not challenger_tier:
            await interaction.response.send_message(
                "You don't have a tier role yet — ask a supervisor to assign one.", ephemeral=True
            )
            return
        if not challenged_tier:
            await interaction.response.send_message(f"{opponent.mention} doesn't have a tier role yet.", ephemeral=True)
            return

        existing = await challenges_db.get_active_challenge_for(str(challenger.id))
        if existing:
            await interaction.response.send_message(
                "You're already in an active challenge. Finish that one first.", ephemeral=True
            )
            return
        existing_opp = await challenges_db.get_active_challenge_for(str(opponent.id))
        if existing_opp:
            await interaction.response.send_message(
                f"{opponent.mention} already has an active challenge pending.", ephemeral=True
            )
            return

        cooldown_until = await players_db.get_cooldown(challenger.id)
        result = can_challenge(
            challenger_tier=challenger_tier,
            challenged_tier=challenged_tier,
            challenger_cooldown_until=cooldown_until,
        )
        if not result.allowed:
            await interaction.response.send_message(result.reason, ephemeral=True)
            return

        challenge = await challenges_db.create_challenge(
            guild_id=str(interaction.guild_id),
            channel_id=str(interaction.channel_id),
            challenger_id=str(challenger.id),
            challenged_id=str(opponent.id),
        )

        view = ChallengeResponseView(challenge.id, opponent.id)
        embed = challenge_request_embed(challenger, opponent, challenger_tier, challenged_tier, "pending")
        msg = await interaction.channel.send(content=opponent.mention, embed=embed, view=view)
        await challenges_db.set_message_refs(challenge.id, request_message_id=str(msg.id))

        await interaction.response.send_message(f"Challenge #{challenge.id} sent!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Challenges(bot))
