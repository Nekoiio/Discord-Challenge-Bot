from __future__ import annotations

import discord

import database.challenges as challenges_db
import services
from config import CFG
from ui.embeds import (
    match_control_embed,
    supervisor_notify_embed,
)
from utils.checks import is_supervisor


class ChallengeResponseView(discord.ui.View):
    """Posted in the channel the /challenge was used in. Only the challenged player can respond."""

    def __init__(self, challenge_id: int, challenged_id: int):
        super().__init__(timeout=None)
        self.challenge_id = challenge_id
        self.challenged_id = challenged_id

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message(
                "Only the challenged player can respond to this.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="challenge_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard(interaction):
            return
        challenge = await challenges_db.get_challenge(self.challenge_id)
        if challenge.status != "pending":
            await interaction.response.send_message("This challenge is no longer pending.", ephemeral=True)
            return

        await challenges_db.update_status(self.challenge_id, "accepted", responded_at=discord.utils.utcnow())

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        challenge = await challenges_db.get_challenge(self.challenge_id)
        await services.refresh_request_card(interaction.guild, challenge)

        await interaction.followup.send(
            "✅ Challenge accepted! A supervisor needs to claim this match before it can start "
            "— check the supervisor channel.",
        )

        guild = interaction.guild
        challenger = await guild.fetch_member(int(challenge.challenger_id))
        challenged = await guild.fetch_member(int(challenge.challenged_id))
        supervisor_channel = await services.get_supervisor_channel(guild)
        if supervisor_channel:
            view = SupervisorClaimView(self.challenge_id)
            msg = await supervisor_channel.send(
                embed=supervisor_notify_embed(challenge, challenger, challenged), view=view
            )
            await challenges_db.set_message_refs(self.challenge_id, supervisor_message_id=str(msg.id))

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, custom_id="challenge_decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard(interaction):
            return
        challenge = await challenges_db.get_challenge(self.challenge_id)
        if challenge.status != "pending":
            await interaction.response.send_message("This challenge is no longer pending.", ephemeral=True)
            return

        winner, loser, role_swap_error = await services.award_forfeit_win(interaction.guild, challenge)

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        challenge = await challenges_db.get_challenge(self.challenge_id)
        await services.refresh_all_cards(interaction.guild, challenge)

        msg = (
            f"❌ Challenge declined. {winner.mention} wins by default and "
            f"{loser.mention} is on cooldown for {CFG.challenge_cooldown_days} days."
        )
        if role_swap_error:
            msg += f"\n⚠️ {role_swap_error}"
        await interaction.followup.send(msg)


class SupervisorClaimView(discord.ui.View):
    """Posted in the supervisor-only channel once a challenge is accepted."""

    def __init__(self, challenge_id: int):
        super().__init__(timeout=None)
        self.challenge_id = challenge_id

    @discord.ui.button(label="Claim as Supervisor", style=discord.ButtonStyle.primary, custom_id="supervisor_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_supervisor(interaction.user):
            await interaction.response.send_message(
                "Only members with the Supervisor role can claim a match.", ephemeral=True
            )
            return

        challenge = await challenges_db.get_challenge(self.challenge_id)
        if challenge.supervisor_id:
            await interaction.response.send_message(
                f"Already claimed by <@{challenge.supervisor_id}>.", ephemeral=True
            )
            return

        await challenges_db.set_supervisor(self.challenge_id, str(interaction.user.id))
        await challenges_db.update_status(self.challenge_id, "in_progress")

        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)

        guild = interaction.guild
        challenge = await challenges_db.get_challenge(self.challenge_id)
        challenger = await guild.fetch_member(int(challenge.challenger_id))
        challenged = await guild.fetch_member(int(challenge.challenged_id))

        # Private thread instead of a standalone channel -- only the two
        # players and the assigned supervisor are added to it.
        thread = await services.create_match_thread(guild, challenge, challenger, challenged, interaction.user)
        await challenges_db.set_message_refs(self.challenge_id, thread_id=str(thread.id))
        await services.post_tracker_card(guild, challenge)

        await thread.send(
            f"{challenger.mention} {challenged.mention} — {interaction.user.mention} will be "
            f"supervising this match. Agree on a server between yourselves, then the supervisor "
            f"will track the score below."
        )

        control_view = MatchControlView(self.challenge_id)
        challenge = await challenges_db.get_challenge(self.challenge_id)
        panel_msg = await thread.send(
            embed=match_control_embed(challenge, challenger, challenged), view=control_view
        )
        await challenges_db.set_message_refs(self.challenge_id, match_message_id=str(panel_msg.id))

        challenge = await challenges_db.get_challenge(self.challenge_id)
        await services.refresh_request_card(guild, challenge)

        await interaction.followup.send(f"Match thread created: {thread.mention}", ephemeral=True)


class GameOverConfirmView(discord.ui.View):
    """
    Shown when a point puts someone's score above the win threshold (usually
    a +2/+3 misclick). The supervisor has to explicitly confirm before the
    game is banked, instead of it closing out automatically.
    """

    def __init__(self, challenge_id: int, parent_view: "MatchControlView"):
        super().__init__(timeout=300)
        self.challenge_id = challenge_id
        self.parent_view = parent_view

    async def _guard(self, interaction: discord.Interaction) -> challenges_db.Challenge | None:
        challenge = await challenges_db.get_challenge(self.challenge_id)
        if challenge is None or challenge.status != "in_progress":
            await interaction.response.send_message("This match isn't active anymore.", ephemeral=True)
            return None
        if str(interaction.user.id) != challenge.supervisor_id:
            await interaction.response.send_message(
                "Only the assigned supervisor can confirm this.", ephemeral=True
            )
            return None
        return challenge

    @discord.ui.button(label="Finalize Game", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        challenge = await self._guard(interaction)
        if not challenge:
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        challenge, winner_side = await services.confirm_close_out_game(self.challenge_id)
        finished = await self.parent_view._finish_if_over(interaction, winner_side, challenge)
        if not finished:
            await self.parent_view._refresh_cards(interaction, challenge)

    @discord.ui.button(label="Not Yet", style=discord.ButtonStyle.secondary)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        challenge = await self._guard(interaction)
        if not challenge:
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="Okay — use the Undo buttons to fix the score, then continue.", view=self
        )


class MatchControlView(discord.ui.View):
    """
    Lives inside the match thread. Only the assigned supervisor can use these
    buttons: +1/+2/+3 per player, Undo per player, and Cancel Match.
    """

    def __init__(self, challenge_id: int):
        super().__init__(timeout=None)
        self.challenge_id = challenge_id

        for side, label, row in (("p1", "Challenger", 0), ("p2", "Challenged", 1)):
            for delta in (1, 2, 3):
                btn = discord.ui.Button(
                    label=f"+{delta} {label}",
                    style=discord.ButtonStyle.secondary,
                    row=row,
                    custom_id=f"mc_pt_{side}_{delta}_{challenge_id}",
                )
                btn.callback = self._make_point_callback(side, delta)
                self.add_item(btn)

            undo_btn = discord.ui.Button(
                label=f"Undo {label}",
                style=discord.ButtonStyle.secondary,
                row=2,
                custom_id=f"mc_undo_{side}_{challenge_id}",
            )
            undo_btn.callback = self._make_undo_callback(side)
            self.add_item(undo_btn)

        cancel_btn = discord.ui.Button(
            label="Cancel Match",
            style=discord.ButtonStyle.danger,
            row=3,
            custom_id=f"mc_cancel_{challenge_id}",
        )
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    def _make_point_callback(self, side: str, delta: int):
        async def callback(interaction: discord.Interaction):
            await self._handle_point(interaction, side, delta)
        return callback

    def _make_undo_callback(self, side: str):
        async def callback(interaction: discord.Interaction):
            await self._handle_undo(interaction, side)
        return callback

    async def _guard(self, interaction: discord.Interaction) -> challenges_db.Challenge | None:
        challenge = await challenges_db.get_challenge(self.challenge_id)
        if challenge is None or challenge.status != "in_progress":
            await interaction.response.send_message("This match isn't active anymore.", ephemeral=True)
            return None
        if str(interaction.user.id) != challenge.supervisor_id:
            await interaction.response.send_message(
                "Only the assigned supervisor can update the score.", ephemeral=True
            )
            return None
        return challenge

    async def _refresh_cards(self, interaction: discord.Interaction, challenge: challenges_db.Challenge):
        await services.refresh_all_cards(interaction.guild, challenge)

    async def _finish_if_over(
        self, interaction: discord.Interaction, winner_side: str | None, challenge: challenges_db.Challenge
    ) -> bool:
        if winner_side is None:
            return False
        winner, loser, role_swap_error = await services.finalize_match(interaction.guild, challenge, winner_side)
        for item in self.children:
            item.disabled = True
        if role_swap_error:
            await interaction.channel.send(f"⚠️ {role_swap_error}")
        challenge = await challenges_db.get_challenge(challenge.id)
        await services.finish_match_and_cleanup(interaction.guild, challenge, winner, loser)
        return True

    async def _handle_point(self, interaction: discord.Interaction, side: str, delta: int):
        challenge = await self._guard(interaction)
        if not challenge:
            return
        await interaction.response.defer()

        await services.apply_score_change(self.challenge_id, side, delta)
        challenge, action, winner_side = await services.try_close_out_game(self.challenge_id)

        if action == "needs_confirmation":
            confirm_view = GameOverConfirmView(self.challenge_id, self)
            await interaction.channel.send(
                f"⚠️ Score is now **{challenge.p1_points}-{challenge.p2_points}** — above "
                f"{CFG.points_to_win_game}. Finalize this game with the current leader as the winner?",
                view=confirm_view,
            )
            await self._refresh_cards(interaction, challenge)
            return

        if action == "closed":
            if await self._finish_if_over(interaction, winner_side, challenge):
                return

        await self._refresh_cards(interaction, challenge)

    async def _handle_undo(self, interaction: discord.Interaction, side: str):
        challenge = await self._guard(interaction)
        if not challenge:
            return
        await interaction.response.defer()
        challenge = await services.apply_score_change(self.challenge_id, side, -1)
        await self._refresh_cards(interaction, challenge)

    async def _cancel(self, interaction: discord.Interaction):
        challenge = await self._guard(interaction)
        if not challenge:
            return
        await challenges_db.update_status(self.challenge_id, "cancelled")
        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        challenge = await challenges_db.get_challenge(self.challenge_id)
        await services.cancel_match_and_cleanup(interaction.guild, challenge, view=self)
