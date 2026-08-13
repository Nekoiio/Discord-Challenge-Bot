from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from database.db import get_db
from utils.checks import is_supervisor


class Tickets(commands.Cog):
    """
    Lightweight absence-justification tickets. Opens a private thread with the
    supervisor role so the player can explain (e.g. "I was hospitalized, please
    don't count my missed challenge as a loss") without it being public.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket", description="Open a support ticket (e.g. to justify a missed challenge).")
    @app_commands.describe(reason="Briefly explain why you need support.")
    async def ticket(self, interaction: discord.Interaction, reason: str):
        db = get_db()
        now = datetime.now().isoformat()
        cur = await db.execute(
            "INSERT INTO tickets (guild_id, user_id, reason, created_at) VALUES (?, ?, ?, ?)",
            (str(interaction.guild_id), str(interaction.user.id), reason, now),
        )
        await db.commit()
        ticket_id = cur.lastrowid

        thread = await interaction.channel.create_thread(
            name=f"ticket-{ticket_id}-{interaction.user.display_name}"[:95],
            type=discord.ChannelType.private_thread,
        )
        await thread.add_user(interaction.user)
        await db.execute("UPDATE tickets SET thread_id = ? WHERE id = ?", (str(thread.id), ticket_id))
        await db.commit()

        await thread.send(
            f"🎫 **Ticket #{ticket_id}** opened by {interaction.user.mention}\n\n**Reason:** {reason}\n\n"
            f"A supervisor will review this shortly."
        )
        await interaction.response.send_message(f"Ticket opened: {thread.mention}", ephemeral=True)

    @app_commands.command(name="resolveticket", description="[Supervisor] Mark a ticket as resolved.")
    @app_commands.describe(ticket_id="The ticket number to resolve.")
    async def resolveticket(self, interaction: discord.Interaction, ticket_id: int):
        if not is_supervisor(interaction.user):
            await interaction.response.send_message("Supervisors only.", ephemeral=True)
            return
        db = get_db()
        await db.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        await db.commit()
        await interaction.response.send_message(f"Ticket #{ticket_id} marked resolved.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
