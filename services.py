"""
Orchestration layer sitting between the Discord-facing code (cogs/, ui/views.py)
and the database/logic layers. Keeping this separate means the button
callbacks and slash commands stay thin, and the actual "what happens when a
challenge is accepted / a point is scored / a match ends" logic lives in one
readable place.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import discord

import database.challenges as challenges_db
import database.players as players_db
from config import CFG
from ui.embeds import (
    challenge_request_embed,
    match_control_embed,
    match_result_embed,
    supervisor_notify_embed,
    tracker_embed,
)
from utils.ladder_logic import (
    compute_cooldown_expiry,
    game_winner,
    match_winner,
    tier_swap_result,
)
from utils.tiers import get_member_tier, set_member_tier

MATCH_THREADS_HUB_NAME = "match-threads"


async def get_supervisor_channel(guild: discord.Guild) -> discord.TextChannel:
    return guild.get_channel(CFG.supervisor_channel_id)


async def get_tracker_channel(guild: discord.Guild) -> discord.TextChannel:
    return guild.get_channel(CFG.tracker_channel_id)


async def _get_or_create_threads_hub(guild: discord.Guild) -> discord.TextChannel:
    """
    Private threads need a parent text channel. We keep one dedicated,
    Supervisor-only "hub" channel inside the configured category and spawn
    a private thread per match from it, rather than making a whole new
    channel per match.
    """
    category = guild.get_channel(CFG.challenge_category_id)
    existing = discord.utils.get(
        (category.text_channels if category else guild.text_channels),
        name=MATCH_THREADS_HUB_NAME,
    )
    if existing:
        return existing

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            create_private_threads=True,
            manage_threads=True,
            embed_links=True,
        ),
        guild.get_role(CFG.supervisor_role_id): discord.PermissionOverwrite(
            view_channel=True, send_messages=True, create_private_threads=True
        ),
    }
    return await guild.create_text_channel(
        name=MATCH_THREADS_HUB_NAME,
        category=category,
        overwrites=overwrites,
        topic="Match threads are spawned from here — players are added individually per match.",
    )


async def create_match_thread(
    guild: discord.Guild,
    challenge: challenges_db.Challenge,
    challenger: discord.Member,
    challenged: discord.Member,
    supervisor: discord.Member,
) -> discord.Thread:
    """
    Creates a private thread for this match, visible only to the two
    players and the assigned supervisor (private threads are membership-based,
    not permission-overwrite-based, so we explicitly add each of them).
    """
    hub = await _get_or_create_threads_hub(guild)
    thread = await hub.create_thread(
        name=f"match-{challenge.id}-{challenger.display_name}-vs-{challenged.display_name}"[:95],
        type=discord.ChannelType.private_thread,
        invitable=False,
        auto_archive_duration=1440,
        reason=f"Challenge #{challenge.id}",
    )
    for member in (challenger, challenged, supervisor):
        try:
            await thread.add_user(member)
        except discord.HTTPException:
            pass
    return thread


async def delete_match_thread(thread: discord.Thread, *, final_message: str | None = None) -> None:
    """Posts a closing message (if given), waits briefly so it's visible, then deletes the thread."""
    if final_message:
        try:
            await thread.send(final_message)
        except discord.HTTPException:
            pass
    await asyncio.sleep(5)
    try:
        await thread.delete()
    except discord.HTTPException:
        pass


async def post_tracker_card(guild: discord.Guild, challenge: challenges_db.Challenge) -> None:
    tracker_channel = await get_tracker_channel(guild)
    if tracker_channel is None:
        return
    challenger = await guild.fetch_member(int(challenge.challenger_id))
    challenged = await guild.fetch_member(int(challenge.challenged_id))
    msg = await tracker_channel.send(embed=tracker_embed(challenge, challenger, challenged))
    await challenges_db.set_message_refs(challenge.id, tracker_message_id=str(msg.id))


async def refresh_tracker_card(guild: discord.Guild, challenge: challenges_db.Challenge) -> None:
    if not challenge.tracker_message_id:
        return
    tracker_channel = await get_tracker_channel(guild)
    if tracker_channel is None:
        return
    try:
        msg = await tracker_channel.fetch_message(int(challenge.tracker_message_id))
    except discord.NotFound:
        return
    challenger = await guild.fetch_member(int(challenge.challenger_id))
    challenged = await guild.fetch_member(int(challenge.challenged_id))
    await msg.edit(embed=tracker_embed(challenge, challenger, challenged))


async def refresh_request_card(guild: discord.Guild, challenge: challenges_db.Challenge) -> None:
    """Re-renders the original Accept/Decline embed so its Status field stays accurate."""
    if not challenge.request_message_id:
        return
    channel = guild.get_channel(int(challenge.channel_id))
    if channel is None:
        return
    try:
        msg = await channel.fetch_message(int(challenge.request_message_id))
    except discord.NotFound:
        return
    challenger = await guild.fetch_member(int(challenge.challenger_id))
    challenged = await guild.fetch_member(int(challenge.challenged_id))
    embed = challenge_request_embed(
        challenger, challenged, get_member_tier(challenger), get_member_tier(challenged), challenge.status
    )
    await msg.edit(embed=embed)


async def refresh_supervisor_card(guild: discord.Guild, challenge: challenges_db.Challenge) -> None:
    """Re-renders the supervisor-channel claim embed so its Status field stays accurate."""
    if not challenge.supervisor_message_id:
        return
    channel = await get_supervisor_channel(guild)
    if channel is None:
        return
    try:
        msg = await channel.fetch_message(int(challenge.supervisor_message_id))
    except discord.NotFound:
        return
    challenger = await guild.fetch_member(int(challenge.challenger_id))
    challenged = await guild.fetch_member(int(challenge.challenged_id))
    await msg.edit(embed=supervisor_notify_embed(challenge, challenger, challenged))


async def refresh_match_panel(guild: discord.Guild, challenge: challenges_db.Challenge, view: discord.ui.View | None = None) -> None:
    """Re-renders the score-control panel inside the match thread, wherever it lives."""
    if not challenge.thread_id or not challenge.match_message_id:
        return
    thread = guild.get_channel_or_thread(int(challenge.thread_id))
    if thread is None:
        return
    try:
        msg = await thread.fetch_message(int(challenge.match_message_id))
    except discord.NotFound:
        return
    challenger = await guild.fetch_member(int(challenge.challenger_id))
    challenged = await guild.fetch_member(int(challenge.challenged_id))
    embed = match_control_embed(challenge, challenger, challenged)
    if view is not None:
        await msg.edit(embed=embed, view=view)
    else:
        await msg.edit(embed=embed)


async def refresh_all_cards(guild: discord.Guild, challenge: challenges_db.Challenge, view: discord.ui.View | None = None) -> None:
    """Keeps every visible embed for this challenge (request/supervisor/tracker/match panel) in sync."""
    await refresh_request_card(guild, challenge)
    await refresh_supervisor_card(guild, challenge)
    await refresh_tracker_card(guild, challenge)
    await refresh_match_panel(guild, challenge, view)


async def apply_score_change(challenge_id: int, side: str, delta: int) -> challenges_db.Challenge:
    if delta > 0:
        return await challenges_db.add_point(challenge_id, side, amount=delta)
    return await challenges_db.undo_point(challenge_id, side)


async def try_close_out_game(challenge_id: int) -> tuple[challenges_db.Challenge, str | None, str | None]:
    """
    Checks whether the current game should close out. Returns
    (challenge, action, winner_side):
      - action is None: game continues, nothing to do.
      - action is 'needs_confirmation': someone's score is above the win
        threshold (likely a misclick on +2/+3) -- caller should ask the
        supervisor to confirm before banking the game, rather than closing
        it automatically.
      - action is 'closed': the game was banked automatically (exact win,
        no overshoot). winner_side is set if the whole match is now over.
    """
    challenge = await challenges_db.get_challenge(challenge_id)
    p1, p2 = challenge.p1_points, challenge.p2_points

    if p1 > CFG.points_to_win_game or p2 > CFG.points_to_win_game:
        return challenge, "needs_confirmation", None

    side = game_winner(p1, p2, CFG.points_to_win_game)
    if side is None:
        return challenge, None, None

    challenge = await challenges_db.finalize_current_game(challenge_id)
    winner_side = match_winner(challenge.game_scores, CFG.games_to_win_match)
    return challenge, "closed", winner_side


async def confirm_close_out_game(challenge_id: int) -> tuple[challenges_db.Challenge, str | None]:
    """Supervisor-confirmed version of banking an over-threshold game. Returns (challenge, winner_side)."""
    challenge = await challenges_db.finalize_current_game(challenge_id)
    winner_side = match_winner(challenge.game_scores, CFG.games_to_win_match)
    return challenge, winner_side


async def finalize_match(
    guild: discord.Guild, challenge: challenges_db.Challenge, winner_side: str
) -> tuple[discord.Member, discord.Member, str | None]:
    """
    Applies the tier swap/cooldown, records the winner, returns
    (winner, loser, role_swap_error). role_swap_error is None on success, or a
    human-readable string if the bot couldn't move the roles (e.g. missing
    Manage Roles permission or the bot's role sits below the tier roles) --
    the match result and cooldown are still recorded either way.
    """
    challenger = await guild.fetch_member(int(challenge.challenger_id))
    challenged = await guild.fetch_member(int(challenge.challenged_id))

    winner_id = challenge.challenger_id if winner_side == "p1" else challenge.challenged_id
    loser_id = challenge.challenged_id if winner_side == "p1" else challenge.challenger_id
    winner_member = challenger if winner_side == "p1" else challenged
    loser_member = challenged if winner_side == "p1" else challenger

    await challenges_db.set_winner(challenge.id, winner_id)

    role_swap_error: str | None = None

    # Tiers only change hands when the lower-ranked challenger wins.
    # (Within the t500 pool this is a same-tier no-op.)
    if winner_id == challenge.challenger_id:
        challenger_tier = get_member_tier(challenger)
        challenged_tier = get_member_tier(challenged)
        new_challenger_tier, new_challenged_tier = tier_swap_result(
            challenger_tier, challenged_tier
        )
        try:
            if new_challenger_tier != challenger_tier:
                await set_member_tier(challenger, new_challenger_tier)
            if new_challenged_tier != challenged_tier:
                await set_member_tier(challenged, new_challenged_tier)
        except discord.Forbidden:
            role_swap_error = (
                "I couldn't update tier roles — I'm missing **Manage Roles**, or my "
                "role needs to be moved **above** the tier roles in Server Settings → Roles."
            )

    now = datetime.now(timezone.utc)
    cooldown_until = compute_cooldown_expiry(now, CFG.challenge_cooldown_days)
    await players_db.set_cooldown(loser_id, cooldown_until)

    return winner_member, loser_member, role_swap_error


async def award_forfeit_win(guild: discord.Guild, challenge: challenges_db.Challenge) -> tuple[discord.Member, discord.Member, str | None]:
    """Used when the challenged player never responds/refuses in time -> challenger wins by default."""
    return await finalize_match(guild, challenge, winner_side="p1")


async def finish_match_and_cleanup(
    guild: discord.Guild,
    challenge: challenges_db.Challenge,
    winner: discord.Member,
    loser: discord.Member,
    view: discord.ui.View | None = None,
) -> None:
    """
    Common "the match just ended" wrap-up: refresh every card to show
    Completed (disabling the score panel's buttons if a view is given),
    post the final result somewhere permanent, then delete the match thread.
    """
    challenge = await challenges_db.get_challenge(challenge.id)
    await refresh_all_cards(guild, challenge, view=view)

    origin_channel = guild.get_channel(int(challenge.channel_id))
    if origin_channel:
        try:
            await origin_channel.send(embed=match_result_embed(challenge, winner, loser))
        except discord.HTTPException:
            pass

    if challenge.thread_id:
        thread = guild.get_channel_or_thread(int(challenge.thread_id))
        if thread:
            await delete_match_thread(
                thread,
                final_message=(
                    f"🏁 Match complete — **{winner.display_name}** defeats {loser.display_name}. "
                    f"This thread will be deleted shortly."
                ),
            )


async def cancel_match_and_cleanup(
    guild: discord.Guild, challenge: challenges_db.Challenge, view: discord.ui.View | None = None
) -> None:
    """Same wrap-up as finish_match_and_cleanup, but for a cancelled (not completed) match."""
    challenge = await challenges_db.get_challenge(challenge.id)
    await refresh_all_cards(guild, challenge, view=view)

    if challenge.thread_id:
        thread = guild.get_channel_or_thread(int(challenge.thread_id))
        if thread:
            await delete_match_thread(
                thread, final_message="🚫 This match was cancelled. This thread will be deleted shortly."
            )
