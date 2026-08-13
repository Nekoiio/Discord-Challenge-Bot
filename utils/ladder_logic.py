"""
Pure functions implementing the ranking rules from the CHALLENGE RULES sheet.
No Discord or database dependencies here on purpose -- this is the one file
that encodes "the rules" and it should be trivially testable/readable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# Highest tier first. Kept here (not just in utils/tiers.py) so this file
# stays a self-contained, dependency-free description of "the rules".
TIER_ORDER = ["t1", "t2", "t3", "t500"]

POOL_TIER = "t500"  # the tier where anyone can challenge anyone else in it


@dataclass(frozen=True)
class EligibilityResult:
    allowed: bool
    reason: str = ""


def can_challenge(
    *,
    challenger_tier: str | None,
    challenged_tier: str | None,
    challenger_cooldown_until: datetime | None,
    now: datetime | None = None,
) -> EligibilityResult:
    """
    Implements:
      - t500 players may challenge anyone else in t500.
      - t1/t2/t3 players may only challenge the tier directly above their own
        (t3 -> t2, t2 -> t1). t1 has nothing above it.
      - A player on cooldown (lost their last challenge < N days ago) cannot
        issue a new challenge.
    """
    now = now or datetime.now(timezone.utc)

    if challenger_tier is None:
        return EligibilityResult(False, "You don't have a tier role yet — ask a supervisor.")
    if challenged_tier is None:
        return EligibilityResult(False, "That player doesn't have a tier role yet.")

    if challenger_cooldown_until and now < challenger_cooldown_until:
        remaining = challenger_cooldown_until - now
        hours = int(remaining.total_seconds() // 3600)
        return EligibilityResult(
            False,
            f"You're on cooldown from a recent loss. Try again in ~{hours}h.",
        )

    if challenger_tier == POOL_TIER:
        if challenged_tier != POOL_TIER:
            return EligibilityResult(
                False, f"As a {POOL_TIER} player you may only challenge other {POOL_TIER} players."
            )
        return EligibilityResult(True)

    idx = TIER_ORDER.index(challenger_tier)
    if idx == 0:
        return EligibilityResult(False, "You're already in the top tier — no one to challenge above you.")

    required_tier = TIER_ORDER[idx - 1]
    if challenged_tier != required_tier:
        return EligibilityResult(
            False, f"You may only challenge players in {required_tier}."
        )
    return EligibilityResult(True)


def compute_cooldown_expiry(now: datetime, cooldown_days: int) -> datetime:
    return now + timedelta(days=cooldown_days)


def compute_response_deadline(created_at: datetime, timeout_days: int) -> datetime:
    return created_at + timedelta(days=timeout_days)


def tier_swap_result(challenger_tier: str, challenged_tier: str) -> tuple[str, str]:
    """
    Winner of a challenge takes the loser's tier; loser drops into the
    winner's old tier. Returns (new_challenger_tier, new_challenged_tier)
    for the case where the CHALLENGER won. (Within the t500 pool both tiers
    are the same, so this is a harmless no-op.)
    """
    return challenged_tier, challenger_tier


def game_winner(p1_points: int, p2_points: int, points_to_win: int) -> str | None:
    """Returns 'p1', 'p2', or None if the game isn't over yet."""
    if p1_points >= points_to_win and p1_points - p2_points >= 1:
        return "p1"
    if p2_points >= points_to_win and p2_points - p1_points >= 1:
        return "p2"
    return None


def match_winner(game_scores: list[tuple[int, int]], games_to_win: int) -> str | None:
    """game_scores is a list of (p1_score, p2_score) completed games."""
    p1_wins = sum(1 for p1, p2 in game_scores if p1 > p2)
    p2_wins = sum(1 for p1, p2 in game_scores if p2 > p1)
    if p1_wins >= games_to_win:
        return "p1"
    if p2_wins >= games_to_win:
        return "p2"
    return None
