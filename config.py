"""
Central configuration for the ranking bot.
Everything here is loaded from environment variables (see .env.example)
so no secrets or server-specific IDs are hardcoded in the source.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int | None = None) -> int | None:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return int(val)


@dataclass(frozen=True)
class Config:
    # Auth
    bot_token: str

    # Server structure
    guild_id: int
    supervisor_role_id: int
    supervisor_channel_id: int          # embeds notifying supervisors of new challenges
    tracker_channel_id: int             # read-only channel showing live challenge scores
    challenge_category_id: int          # category where match threads get created
    ladder_display_channel_id: int      # channel where the auto-updating ladder message lives
    ladder_update_interval_minutes: int  # how often the background loop refreshes it

    # Tiers are Discord roles, ordered highest -> lowest. "t500" is the pool
    # tier where anyone can challenge anyone else in it (like old "Tier 3").
    tier_role_ids: dict[str, int]

    # Rules
    challenge_cooldown_days: int
    challenge_response_timeout_days: int
    points_to_win_game: int
    games_to_win_match: int

    db_path: str


def load_config() -> Config:
    return Config(
        bot_token=os.environ["DISCORD_BOT_TOKEN"],
        guild_id=_env_int("GUILD_ID"),
        supervisor_role_id=_env_int("SUPERVISOR_ROLE_ID"),
        supervisor_channel_id=_env_int("SUPERVISOR_CHANNEL_ID"),
        tracker_channel_id=_env_int("TRACKER_CHANNEL_ID"),
        challenge_category_id=_env_int("CHALLENGE_CATEGORY_ID"),
        ladder_display_channel_id=_env_int("LADDER_DISPLAY_CHANNEL_ID"),
        ladder_update_interval_minutes=_env_int("LADDER_UPDATE_INTERVAL_MINUTES", 10),
        tier_role_ids={
            "t1": _env_int("TIER1_ROLE_ID"),
            "t2": _env_int("TIER2_ROLE_ID"),
            "t3": _env_int("TIER3_ROLE_ID"),
            "t500": _env_int("TIER500_ROLE_ID"),
        },
        challenge_cooldown_days=_env_int("CHALLENGE_COOLDOWN_DAYS", 3),
        challenge_response_timeout_days=_env_int("CHALLENGE_RESPONSE_TIMEOUT_DAYS", 2),
        points_to_win_game=_env_int("POINTS_TO_WIN_GAME", 21),
        games_to_win_match=_env_int("GAMES_TO_WIN_MATCH", 2),
        db_path=os.getenv("DB_PATH", "ranking.db"),
    )


CFG = load_config()
