-- Tier lives on Discord roles (Le t1/t2/t3/t500). This table tracks
-- per-player state that Discord roles can't hold: the challenge cooldown
-- after a loss, a player's rank *within* their current tier (1 = top of
-- that tier), and their jersey number.
CREATE TABLE IF NOT EXISTS players (
    discord_id      TEXT PRIMARY KEY,
    cooldown_until  TEXT,                  -- ISO datetime, NULL if not on cooldown
    tier_rank       INTEGER,               -- rank within whatever tier they're currently in
    jersey_number   INTEGER                -- optional, admin-set
);

CREATE TABLE IF NOT EXISTS challenges (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id            TEXT NOT NULL,
    channel_id          TEXT NOT NULL,           -- channel the /challenge command was used in
    challenger_id       TEXT NOT NULL,
    challenged_id       TEXT NOT NULL,
    status              TEXT NOT NULL,           -- pending, declined, expired, accepted,
                                                  -- in_progress, complete, cancelled
    created_at          TEXT NOT NULL,
    responded_at        TEXT,
    server_agreed       TEXT,                    -- free-text server name, mutual agreement
    supervisor_id       TEXT,
    thread_id           TEXT,                     -- the match thread's channel id
    match_message_id    TEXT,                     -- the score-control panel message inside the thread
    tracker_message_id  TEXT,                     -- message in the read-only tracker channel
    request_message_id  TEXT,                    -- accept/decline embed message
    supervisor_message_id TEXT,                  -- embed in supervisor channel

    current_game        INTEGER NOT NULL DEFAULT 1,
    p1_points           INTEGER NOT NULL DEFAULT 0,   -- challenger points, current game
    p2_points           INTEGER NOT NULL DEFAULT 0,   -- challenged points, current game
    game_scores         TEXT NOT NULL DEFAULT '[]',   -- JSON list of [p1,p2] completed games

    winner_id           TEXT,

    FOREIGN KEY (challenger_id) REFERENCES players(discord_id),
    FOREIGN KEY (challenged_id) REFERENCES players(discord_id)
);

CREATE TABLE IF NOT EXISTS ladder_display (
    guild_id    TEXT PRIMARY KEY,
    channel_id  TEXT NOT NULL,
    message_id  TEXT             -- NULL until the message has actually been sent once
);

CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    challenge_id INTEGER,
    reason      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',  -- open, resolved
    created_at  TEXT NOT NULL,
    thread_id   TEXT
);
