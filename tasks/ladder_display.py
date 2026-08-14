from __future__ import annotations

from discord.ext import commands, tasks

import services
from config import CFG


class LadderDisplayTask(commands.Cog):
    """
    Periodically re-checks the auto-updating #ladder message: if it's
    missing (first run, or someone deleted it), sends a fresh one; if it's
    there, edits it in place to match current tier role membership. Most
    tier changes also trigger an immediate sync elsewhere (see
    services.finish_match_and_cleanup / cogs/admin.py settier) -- this loop
    is the periodic fallback/consistency check.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_ladder_display.start()

    def cog_unload(self):
        self.sync_ladder_display.cancel()

    @tasks.loop(minutes=CFG.ladder_update_interval_minutes)
    async def sync_ladder_display(self):
        if not CFG.ladder_display_channel_id:
            return
        guild = self.bot.get_guild(CFG.guild_id)
        if guild is None:
            return
        await services.sync_ladder_display(guild)

    @sync_ladder_display.before_loop
    async def before(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LadderDisplayTask(bot))
