from __future__ import annotations

import discord

import database.players as players_db
from config import CFG
from database.challenges import Challenge
from utils.tiers import TIER_LABELS, TIER_ORDER, get_ordered_tier_members

TIER_EMOJI = {"t1": "🥇", "t2": "🥈", "t3": "🥉", "t500": "🔰"}

# Every embed that shows a challenge's status uses exactly one of these four
# labels, so the status always reads the same across every view.
STATUS_DISPLAY = {
    "pending": "🟡 Pending",
    "accepted": "🟡 Pending",
    "in_progress": "🔵 In Progress",
    "complete": "✅ Completed",
    "declined": "✅ Completed",   # forfeit win -- a result was still decided
    "expired": "✅ Completed",    # forfeit win via timeout -- ditto
    "cancelled": "🔴 Cancelled",  # aborted by a supervisor, no result
}


def status_display(status: str) -> str:
    return STATUS_DISPLAY.get(status, status.replace("_", " ").title())


async def ladder_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(title="🏆 Ladder Rankings", color=discord.Color.gold())
    for tier in TIER_ORDER:
        ordered = await get_ordered_tier_members(guild, tier)
        if ordered:
            lines = []
            for member, rank in ordered:
                jersey = await players_db.get_jersey_number(member.id)
                jersey_str = f" • #{jersey}" if jersey is not None else ""
                lines.append(f"**{rank}.** {member.mention}{jersey_str}")
            value = "\n".join(lines)
        else:
            value = "*empty*"
        embed.add_field(
            name=f"{TIER_EMOJI[tier]} {TIER_LABELS[tier]}", value=value, inline=False
        )
    return embed


def challenge_request_embed(
    challenger: discord.Member,
    challenged: discord.Member,
    challenger_tier: str,
    challenged_tier: str,
    status: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Challenge Request",
        description=(
            f"{challenger.mention} ({TIER_LABELS[challenger_tier]}) is challenging "
            f"{challenged.mention} ({TIER_LABELS[challenged_tier]})!\n\n"
            f"**{challenged.mention}**, do you accept? A best-of-3 to "
            f"{CFG.points_to_win_game} awaits."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(name="Status", value=status_display(status), inline=True)
    embed.set_footer(
        text=f"No response within {CFG.challenge_response_timeout_days} days = automatic loss."
    )
    return embed


def supervisor_notify_embed(challenge: Challenge, challenger: discord.abc.User, challenged: discord.abc.User) -> discord.Embed:
    embed = discord.Embed(
        title=f"🧑‍⚖️ Challenge #{challenge.id} needs a supervisor",
        description=f"{challenger.mention} vs {challenged.mention}",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Status", value=status_display(challenge.status), inline=True)
    if challenge.supervisor_id:
        embed.add_field(name="Supervisor", value=f"<@{challenge.supervisor_id}>", inline=True)
    return embed


def match_control_embed(
    challenge: Challenge, challenger: discord.abc.User, challenged: discord.abc.User
) -> discord.Embed:
    embed = discord.Embed(
        title=f"📊 Match #{challenge.id} — Best of {2 * CFG.games_to_win_match - 1}",
        color=discord.Color.green(),
    )
    embed.add_field(name="Challenger", value=challenger.mention, inline=True)
    embed.add_field(name="Challenged", value=challenged.mention, inline=True)
    embed.add_field(name="Status", value=status_display(challenge.status), inline=True)

    completed = "\n".join(
        f"Game {i + 1}: **{p1}–{p2}**" for i, (p1, p2) in enumerate(challenge.game_scores)
    ) or "*No games completed yet*"
    embed.add_field(name="Completed games", value=completed, inline=False)

    embed.add_field(
        name=f"Game {challenge.current_game} (live)",
        value=f"**{challenge.p1_points} – {challenge.p2_points}**",
        inline=False,
    )
    if challenge.server_agreed:
        embed.add_field(name="Server", value=challenge.server_agreed, inline=True)
    if challenge.supervisor_id:
        embed.set_footer(text="Supervised match — only the assigned supervisor can update the score.")
    return embed


def tracker_embed(challenge: Challenge, challenger: discord.abc.User, challenged: discord.abc.User) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️ #{challenge.id}: {challenger.display_name} vs {challenged.display_name}",
        color=discord.Color.teal(),
    )
    completed = ", ".join(f"{p1}-{p2}" for p1, p2 in challenge.game_scores) or "—"
    embed.add_field(name="Games", value=completed, inline=True)
    embed.add_field(
        name="Current",
        value=f"{challenge.p1_points}-{challenge.p2_points}",
        inline=True,
    )
    embed.add_field(name="Status", value=status_display(challenge.status), inline=True)
    if challenge.winner_id:
        embed.add_field(name="Winner", value=f"<@{challenge.winner_id}>", inline=False)
    if challenge.supervisor_id:
        embed.set_footer(text="Supervisor assigned")
    return embed


def match_result_embed(
    challenge: Challenge, winner: discord.abc.User, loser: discord.abc.User
) -> discord.Embed:
    embed = discord.Embed(
        title="🏁 Match Complete",
        description=f"**{winner.mention}** defeats {loser.mention}!",
        color=discord.Color.gold(),
    )
    completed = "\n".join(
        f"Game {i + 1}: {p1}–{p2}" for i, (p1, p2) in enumerate(challenge.game_scores)
    )
    embed.add_field(name="Final score", value=completed or "—", inline=False)
    return embed
