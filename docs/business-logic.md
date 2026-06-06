# Business Logic — NHL Fantasy Points Engine

## What is OfficePools?

OfficePools is a **fantasy sports pool** platform — not a betting site. The distinction matters:

- **Sports betting** — you wager money on the outcome of a real game (e.g. "CAR wins tonight"). Regulated, requires a gambling license.
- **Fantasy sports pool** — you pick real players, and your score is based on how those players actually perform in real games. You compete against other people in your pool, not against the house. Legally treated differently from gambling in most jurisdictions.

OfficePools runs hockey pools. Think of it like a season-long competition between friends, coworkers, or strangers — everyone drafts players, and the person whose players collectively put up the best stats wins the pool.

---

## Hockey Terminology

### TOI — Time On Ice

How many minutes and seconds a player was on the ice during the game. Stored in seconds in our DB.

`"22:14"` from the API → `1334` seconds in our `SkaterStat.toi` column.

Matters for fantasy because a player who only plays 8 minutes has far fewer opportunities to score than one who plays 22 minutes. TOI is a rough proxy for how important a player is to their team.

---

### Skater

Any non-goalie player — forwards (centres, left wings, right wings) and defencemen. They skate around and shoot/pass. The word "skater" is used in hockey to distinguish the 5 outfield players from the goalie.

In our schema, `SkaterStat` covers all positions except `"G"`.

---

### Goalie

The player who guards the net. Completely different job from skaters — they don't shoot or pass, they stop pucks. Their stats are saves, goals against, and save percentage. That's why `GoalieStat` is a separate table with entirely different columns.

---

### PIM — Penalties In Minutes

When a player breaks a rule (hooking, slashing, fighting), they sit in the penalty box for 2 or 5 minutes. PIM is the total penalty minutes accumulated in a game.

Some fantasy pools award points for PIM (encourages physical play). Others ignore it. Our `ScoringRule` table controls whether it counts and how much.

---

### Plus/Minus

A measure of defensive responsibility.

- `+1` every time your team scores a goal while you're on the ice
- `-1` every time the opposing team scores while you're on the ice

A player with `+25` for the season is considered strong defensively. `-15` means they're often on the ice when bad things happen. Heavily used in fantasy scoring.

---

### SOG — Shots on Goal

How many times a player shot the puck and it was on target (would have gone in if the goalie didn't stop it). Shots that miss the net entirely don't count.

Fantasy pools often award 0.5 pts per shot — it rewards players who are active and aggressive even if they don't score.

---

### Power Play Goals (PPG)

A goal scored while the opposing team has a player in the penalty box (so your team has 5 skaters vs their 4). Power play goals are often worth more fantasy points than even-strength goals because they're harder to set up and indicate a skilled player on the power play unit.

---

### Faceoff %

At the start of each period and after every stoppage, a referee drops the puck between two opposing players — a **faceoff**. Winning the faceoff means your team gets possession.

`faceoff_pct` is the percentage of faceoffs a player won. Only relevant for centres (they take most faceoffs). That's why the column is `null=True` in `SkaterStat` — wingers and defencemen rarely take faceoffs.

---

### Blocked Shots

When a defenceman slides in front of a shot to prevent it reaching the goalie. Valued in fantasy pools that reward defensive play.

---

### Giveaways / Takeaways

- **Giveaway** — you had the puck and lost it to the other team (bad)
- **Takeaway** — you took the puck away from the other team (good)

Advanced stats. Not all fantasy pools use them, but they're in the NHL API so we store them.

---

### OT Loss (Goalie Decision)

Games that are tied after 60 minutes go to overtime. The goalie who was in net when the OT goal is scored against them gets an `"O"` (OT Loss) — distinct from a regular loss `"L"` because they kept the team in the game for 60 minutes. Many fantasy pools award 1 point for an OT loss vs 0 for a regulation loss.

`Decision` is only set for the starting goalie who played the majority of the game:

- `"W"` — their team won
- `"L"` — their team lost in regulation
- `"O"` — their team lost in overtime
- `null` — backup goalie who only played a few minutes

---

### Save Percentage (save_pct)

`saves / shots_against` — what fraction of shots the goalie stopped.

`0.920` means the goalie stopped 92% of shots. League average is around `0.900`. Elite goalies are `0.920+`. A bad game might be `0.850`.

---

## Fantasy Scoring — How Points Are Calculated

Each player earns fantasy points based on their real-game performance. The `ScoringRule` table defines how many points each stat is worth.

A typical scoring system:

| Stat         | Player Type | Points |
| ------------ | ----------- | ------ |
| Goal         | Skater      | 4.0    |
| Assist       | Skater      | 2.0    |
| Shot on goal | Skater      | 0.5    |
| Plus/minus   | Skater      | 1.0    |
| PIM          | Skater      | 0.25   |
| Blocked shot | Skater      | 0.5    |
| Win          | Goalie      | 5.0    |
| Save         | Goalie      | 0.2    |
| Goal against | Goalie      | -1.0   |
| OT loss      | Goalie      | 1.0    |

So if Auston Matthews scores 2 goals, 1 assist, and 6 shots in a game:

```
(2 × 4.0) + (1 × 2.0) + (6 × 0.5) = 8 + 2 + 3 = 13.0 fantasy points
```

---

## Why These Stats Are Stored in the DB

The `ScoringRule` table exists because **different pools use different scoring systems**. A casual office pool might only score goals and assists. A hardcore pool might score every stat including giveaways. OfficePools supports both — the scoring weights live in the DB, not in code, so they can be changed per pool without a deployment.

The `fantasy_points` column on `SkaterStat` and `GoalieStat` is a **pre-computed cache** — the scoring engine calculates it once and writes it to the DB so the leaderboard API can just `ORDER BY fantasy_points` without re-running the math on every request.

---

## The Flow End to End

```
1. Real NHL game is played tonight
2. Celery beat task wakes up at 2am
3. Fetches completed games from NHL API
4. Parses player stats and upserts into SkaterStat / GoalieStat
5. NumPy scoring engine loads all stats into a matrix
6. Multiplies by the ScoringRule weight vector
7. Writes fantasy_points back to each row
8. Leaderboard API reads pre-computed fantasy_points → instant response
```
