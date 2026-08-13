from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database.challenges as challenges_db
import services
from utils.checks import is_supervisor
from utils.tiers import TIER_LABELS, TIER_ORDER, set_member_tier


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _find_challenge_id_in_channel(self, interaction: discord.Interaction) -> int | None:
        # Match channels are named "match-<id>-..."
        name = interaction.channel.name
        if name.startswith("match-"):
            try:
                return int(name.split("-")[1])
            except (IndexError, ValueError):
                return None
        return None

    @app_commands.command(name="setserver", description="Record the server both players agreed to play on.")
    @app_commands.describe(server="e.g. 'US-East 3' or a server code/link.")
    async def setserver(self, interaction: discord.Interaction, server: str):
        challenge_id = self._find_challenge_id_in_channel(interaction)
        if challenge_id is None:
            await interaction.response.send_message(
                "This only works inside an active match channel.", ephemeral=True
            )
            return
        await challenges_db.set_server_agreed(challenge_id, server)
        await interaction.response.send_message(f"Server set to **{server}** for this match.")

    @app_commands.command(name="forcewin", description="[Supervisor] Manually set the winner (e.g. approved absence, forfeit).")
    @app_commands.describe(winner="The player who should be awarded the win.")
    async def forcewin(self, interaction: discord.Interaction, winner: discord.Member):
        if not is_supervisor(interaction.user):
            await interaction.response.send_message("Supervisors only.", ephemeral=True)
            return
        challenge_id = self._find_challenge_id_in_channel(interaction)
        if challenge_id is None:
            await interaction.response.send_message(
                "This only works inside an active match channel.", ephemeral=True
            )
            return
        challenge = await challenges_db.get_challenge(challenge_id)
        if str(winner.id) not in (challenge.challenger_id, challenge.challenged_id):
            await interaction.response.send_message("That player isn't part of this match.", ephemeral=True)
            return

        # finish_match_and_cleanup waits a few seconds before deleting the
        # thread, which blows past Discord's 3-second initial-response
        # window -- defer now and reply via followup once it's done.
        await interaction.response.defer()

        side = "p1" if str(winner.id) == challenge.challenger_id else "p2"
        winner_member, loser_member, role_swap_error = await services.finalize_match(interaction.guild, challenge, side)
        if role_swap_error:
            await interaction.channel.send(f"⚠️ {role_swap_error}")
        challenge = await challenges_db.get_challenge(challenge_id)
        await services.finish_match_and_cleanup(interaction.guild, challenge, winner_member, loser_member)
        await interaction.followup.send("Result recorded.")

    @app_commands.command(name="settier", description="[Supervisor] Manually set a player's tier role.")
    @app_commands.describe(member="The player to update.", tier="The tier to assign.")
    @app_commands.choices(tier=[app_commands.Choice(name=TIER_LABELS[t], value=t) for t in TIER_ORDER])
    async def settier(self, interaction: discord.Interaction, member: discord.Member, tier: app_commands.Choice[str]):
        if not is_supervisor(interaction.user):
            await interaction.response.send_message("Supervisors only.", ephemeral=True)
            return
        await set_member_tier(member, tier.value)
        await interaction.response.send_message(f"{member.mention} is now in **{TIER_LABELS[tier.value]}**.")

    @app_commands.command(name="cancelchallenge", description="[Supervisor] Cancel a pending or in-progress challenge.")
    @app_commands.describe(challenge_id="The challenge number to cancel.")
    async def cancelchallenge(self, interaction: discord.Interaction, challenge_id: int):
        if not is_supervisor(interaction.user):
            await interaction.response.send_message("Supervisors only.", ephemeral=True)
            return
        challenge = await challenges_db.get_challenge(challenge_id)
        if not challenge:
            await interaction.response.send_message("No such challenge.", ephemeral=True)
            return
        # cancel_match_and_cleanup waits a few seconds before deleting the
        # thread, which blows past Discord's 3-second initial-response
        # window -- defer now and reply via followup once it's done.
        await interaction.response.defer()

        await challenges_db.update_status(challenge_id, "cancelled")
        challenge = await challenges_db.get_challenge(challenge_id)
        await services.cancel_match_and_cleanup(interaction.guild, challenge)
        await interaction.followup.send(f"Challenge #{challenge_id} cancelled.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
