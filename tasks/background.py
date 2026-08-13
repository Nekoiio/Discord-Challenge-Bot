from __future__ import annotations

from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

import database.challenges as challenges_db
import services
from config import CFG


class BackgroundTasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_stale_challenges.start()

    def cog_unload(self):
        self.check_stale_challenges.cancel()

    @tasks.loop(hours=1)
    async def check_stale_challenges(self):
        cutoff = datetime.now() - timedelta(days=CFG.challenge_response_timeout_days)
        stale = await challenges_db.get_stale_pending(cutoff)

        for challenge in stale:
            guild = self.bot.get_guild(int(challenge.guild_id))
            if guild is None:
                continue

            await challenges_db.update_status(challenge.id, "expired", responded_at=datetime.now())
            winner, loser, role_swap_error = await services.award_forfeit_win(guild, challenge)

            challenge = await challenges_db.get_challenge(challenge.id)
            await services.refresh_all_cards(guild, challenge)

            channel = guild.get_channel(int(challenge.channel_id))
            if channel:
                try:
                    msg = (
                        f"⏱️ Challenge #{challenge.id} timed out — {loser.mention} didn't respond in "
                        f"{CFG.challenge_response_timeout_days} days. {winner.mention} wins by default. "
                        f"(If this was unfair, {loser.mention} can open a `/ticket` to dispute it.)"
                    )
                    if role_swap_error:
                        msg += f"\n⚠️ {role_swap_error}"
                    await channel.send(msg)
                except discord.HTTPException:
                    pass

    @check_stale_challenges.before_loop
    async def before(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(BackgroundTasks(bot))
