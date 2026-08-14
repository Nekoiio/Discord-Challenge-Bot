# ⚔️ Ladder Challenge Bot

A Discord bot that runs a fully automated, tier-based ladder for competitive
1v1 challenges — built for a community that wanted its ranking system to stop
living in someone's head.

Players hold a **tier role** (`t1` → `t500`), challenge the player
above them, and the bot handles the rest: eligibility checks, the
accept/decline flow, spinning up a private match thread, live score
tracking, tier swaps on a win, and cooldowns on a loss — all supervised by a
human referee at every step.

---

## What it actually does

**`/challenge @opponent`**
The bot checks the challenge is legal before it ever reaches a human:
- Are you actually allowed to challenge this person? (Tier rules below)
- Are you on a post-loss cooldown?
- Do either of you already have an active challenge?

If it's a legal challenge, an **Accept / Decline** embed goes out that only
the challenged player can act on.

**Accept → Supervisor claim**
Once accepted, a claim card appears in a dedicated supervisor channel.
Any member with the Supervisor role can claim it — first come, first served.

**Claim → Private match thread**
Claiming spins up a **private thread** visible only to the two players and
the assigned supervisor. Inside, the supervisor drives a live scoring panel:

| Button | What it does |
|---|---|
| `+1 / +2 / +3` per player | Adds points |
| `Undo` per player | Correct a misclick |
| `Cancel Match` | Aborts the match, no result recorded |

Games close out automatically once a player reaches the win threshold — but
if a score somehow overshoots it (an errant `+3`, say), the bot **stops and
asks for confirmation** instead of guessing what happened.

**Win → Tier swap, automatically**
When the match is decided, the winner and loser's tier roles swap on the
spot, the loser gets a configurable cooldown before their next challenge,
and the thread quietly cleans itself up after posting the result.

**Always in sync**
Every card touching a given challenge — the original request, the
supervisor claim post, the live tracker entry, the in-thread score panel —
shows the same four states (`Pending`, `In Progress`, `Completed`,
`Cancelled`) and updates together. Nothing is ever left showing stale info.

---

## The tier system

Tiers are just Discord roles (`t1`, `t2`, `t3`, `t500`), so
promoting/demoting someone manually is as simple as changing their role —
the bot reads tier straight from role membership, there's no separate
ranking database to fall out of sync.

- **`t500`** is an open pool — anyone in it can challenge anyone else in it.
- **`t1` / `t2` / `t3`** are strict — you may only challenge the tier
  directly above your own.
- Win a challenge as the lower tier and you **swap tiers** with your
  opponent on the spot.

## No-shows are handled too

- Decline, or don't respond within a configurable window (default 2 days) →
  automatic forfeit loss.
- `/ticket` opens a private thread with supervisors for absence disputes.
- `/forcewin` and `/cancelchallenge` give supervisors a manual override for
  edge cases.

---

## Tech stack

- **Python 3** + [discord.py](https://github.com/Rapptz/discord.py) (slash
  commands, buttons, private threads)
- **SQLite** via `aiosqlite` for challenge/match state (tiers themselves
  live on Discord roles, not the DB)
- Self-migrating schema — new columns get patched into an existing database
  on startup instead of requiring a manual wipe

## Architecture

The project is split so that "the rules" are easy to find and change
independently of the Discord plumbing:

```
bot.py            Entry point — loads cogs, DB, re-attaches persistent views
config.py         All settings, loaded from environment variables
services.py       Orchestration layer — what happens on accept/point/win

database/         SQLite schema + queries (challenges, cooldowns, tickets)
ui/               Embed builders + all button views
cogs/             Slash commands (ranking, challenges, tickets, admin)
tasks/            Background loop enforcing the no-response timeout
utils/            Pure tier/eligibility/scoring logic + Discord role helpers
```

`utils/ladder_logic.py` in particular has zero Discord or database
dependencies — it's a small, readable, testable description of the rules
themselves (who can challenge whom, when a game/match is won), decoupled
from everything that makes it run on Discord.

---

## Setup

1. Create a bot application at the
   [Discord Developer Portal](https://discord.com/developers/applications),
   enabthe **Server Members Intent**, and invite it with `bot` +
   `applications.commands` scopes (Manage Roles, Manage Channels/Threads,
   Send Messages, Embed Links).
2. `cp .env.example .env` and fill in your bot token, tier role IDs, and
   channel/category IDs.
3. `pip install -r requirements.txt`
4. `python bot.py`

Slash commands sync instantly to your configured guild on startup.

---

*Built as a self-contained ladder system for a Discord community — no
external services, no paid hosting requirements, just Python and SQLite.*
