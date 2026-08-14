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
    # 'cross_tier': challenging into the tier above; 'intra_tier': challenging
    # for a better rank within your own tier (including the t500 pool).
    challenge_type: str | None = None


def can_challenge(
    *,
    challenger_tier: str | None,
    challenged_tier: str | None,
    challenger_tier_rank: int | None,
    challenged_tier_rank: int | None,
    challenger_cooldown_until: datetime | None,
    now: datetime | None = None,
) -> EligibilityResult:
    """
    Implements two ways to issue a legal challenge:
      - Cross-tier: t1/t2/t3 players may challenge anyone in the tier
        directly above their own (t3 -> t2, t2 -> t1). t500 players may
        challenge anyone else in t500 (t500 has no tier above it -- this is
        the open pool).
      - Intra-tier: within t1/t2/t3, a player may also challenge whoever is
        ranked directly above them in their OWN tier, to climb that tier's
        internal ranking without changing tiers. (t500 doesn't need this --
        its pool rule above already lets anyone challenge anyone.)
    A player on cooldown (lost their last challenge < N days ago) cannot
    issue a new challenge of either kind.
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

    # Cross-tier: t500 pool is unrestricted; t1/t2/t3 target the tier above.
    if challenger_tier == POOL_TIER:
        if challenged_tier == POOL_TIER:
            return EligibilityResult(True, challenge_type="cross_tier")
    else:
        idx = TIER_ORDER.index(challenger_tier)
        if idx > 0 and challenged_tier == TIER_ORDER[idx - 1]:
            return EligibilityResult(True, challenge_type="cross_tier")

    # Intra-tier: only meaningful for t1/t2/t3 (t500's pool rule above already
    # covers "anyone in my own tier" unrestricted).
    if challenger_tier == challenged_tier and challenger_tier != POOL_TIER:
        if challenger_tier_rank is not None and challenged_tier_rank is not None:
            if challenged_tier_rank == challenger_tier_rank - 1:
                return EligibilityResult(True, challenge_type="intra_tier")
        return EligibilityResult(
            False, "Within your tier you may only challenge the player ranked directly above you."
        )

    if challenger_tier == POOL_TIER:
        return EligibilityResult(
            False, f"As a {POOL_TIER} player you may only challenge other {POOL_TIER} players."
        )

    idx = TIER_ORDER.index(challenger_tier)
    if idx == 0:
        return EligibilityResult(
            False, "You're already in the top tier — you can only challenge for rank within it."
        )
    required_tier = TIER_ORDER[idx - 1]
    return EligibilityResult(
        False,
        f"You may only challenge players in {required_tier}, "
        f"or the player ranked directly above you in your own tier.",
    )


def compute_cooldown_expiry(now: datetime, cooldown_days: int) -> datetime:
    return now + timedelta(days=cooldown_days)


def compute_response_deadline(created_at: datetime, timeout_days: int) -> datetime:
    return created_at + timedelta(days=timeout_days)


def swap_tier_and_rank(
    challenger_tier: str,
    challenger_rank: int,
    challenged_tier: str,
    challenged_rank: int,
) -> tuple[tuple[str, int], tuple[str, int]]:
    """
    Winner of a challenge takes the loser's exact spot (tier AND rank within
    that tier); loser drops into the winner's old spot. Returns
    ((new_challenger_tier, new_challenger_rank), (new_challenged_tier, new_challenged_rank))
    for the case where the CHALLENGER won. When both players share a tier
    (an intra-tier challenge, or a t500 pool challenge), the tier half of
    this is a no-op and only the ranks actually swap.
    """
    return (challenged_tier, challenged_rank), (challenger_tier, challenger_rank)


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
