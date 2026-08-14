from __future__ import annotations

import logging

import discord
from discord.ext import commands

import database.challenges as challenges_db
from config import CFG
from database.db import init_db
from ui.views import ChallengeResponseView, MatchControlView, SupervisorClaimView

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ranking-bot")

INITIAL_COGS = (
    "cogs.ranking",
    "cogs.challenges",
    "cogs.tickets",
    "cogs.admin",
    "tasks.background",
    "tasks.ladder_display",
)


class RankingBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = False
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await init_db(CFG.db_path)

        for cog in INITIAL_COGS:
            await self.load_extension(cog)
            log.info("Loaded %s", cog)

        await self._reattach_persistent_views()

        if CFG.guild_id:
            guild = discord.Object(id=CFG.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def _reattach_persistent_views(self) -> None:
        """
        Buttons with custom_id + timeout=None only survive a restart if the bot
        re-registers a view instance for each still-open message on startup.
        """
        pending = await challenges_db.get_in_progress()
        for challenge in pending:
            if challenge.status == "pending" and challenge.request_message_id:
                self.add_view(
                    ChallengeResponseView(challenge.id, int(challenge.challenged_id)),
                    message_id=int(challenge.request_message_id),
                )
            if challenge.status == "accepted" and challenge.supervisor_message_id:
                self.add_view(
                    SupervisorClaimView(challenge.id),
                    message_id=int(challenge.supervisor_message_id),
                )
            if challenge.status == "in_progress":
                self.add_view(MatchControlView(challenge.id))

    async def on_ready(self):
        log.info("Logged in as %s (%s)", self.user, self.user.id)


def main():
    bot = RankingBot()
    bot.run(CFG.bot_token)


if __name__ == "__main__":
    main()
