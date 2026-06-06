# NHL API — Endpoint Reference

Base URL: `https://api-web.nhle.com/v1`

No authentication required.

---

## 1. Schedule

**`GET /schedule/{date}`**

Returns all games for a given date. `/schedule/now` redirects to today's date.

### Key fields

```json
{
  "gameWeek": [
    {
      "date": "2026-06-04",
      "games": [
        {
          "id": 2025030412,
          "gameType": 3,
          "gameState": "OFF",
          "startTimeUTC": "2026-06-05T00:00:00Z",
          "awayTeam": { "id": 54, "abbrev": "VGK", "commonName": { "default": "Golden Knights" }, "score": 3 },
          "homeTeam": { "id": 12, "abbrev": "CAR", "commonName": { "default": "Hurricanes" }, "score": 4 }
        }
      ]
    }
  ]
}
```

### Notes
- `id` is an **integer**, not a string
- `gameType`: `2` = regular season, `3` = playoffs, `1` = preseason
- `gameState`: `"OFF"` = final, `"LIVE"` = in progress, `"FUT"` = scheduled, `"PRE"` = pre-game
- Only ingest games where `gameState == "OFF"`

---

## 2. Boxscore

**`GET /gamecenter/{game_id}/boxscore`**

Per-player stats for a completed game. Players are split into three groups per team.

### Key fields

```json
{
  "id": 2025030412,
  "gameDate": "2026-06-04",
  "gameState": "OFF",
  "awayTeam": { "id": 54, "abbrev": "VGK" },
  "homeTeam": { "id": 12, "abbrev": "CAR" },
  "playerByGameStats": {
    "awayTeam": {
      "forwards": [...],
      "defense": [...],
      "goalies": [...]
    },
    "homeTeam": {
      "forwards": [...],
      "defense": [...],
      "goalies": [...]
    }
  }
}
```

### Skater fields (forwards + defense)

```json
{
  "playerId": 8478403,
  "name": { "default": "J. Eichel" },
  "position": "C",
  "goals": 0,
  "assists": 0,
  "points": 0,
  "plusMinus": 0,
  "pim": 0,
  "hits": 1,
  "powerPlayGoals": 0,
  "sog": 0,
  "faceoffWinningPctg": 0.421053,
  "toi": "22:22",
  "blockedShots": 1,
  "shifts": 26,
  "giveaways": 3,
  "takeaways": 0
}
```

### Goalie fields

```json
{
  "playerId": 8475883,
  "name": { "default": "F. Andersen" },
  "position": "G",
  "starter": true,
  "decision": "W",
  "toi": "63:56",
  "shotsAgainst": 26,
  "saves": 23,
  "goalsAgainst": 3,
  "savePctg": 0.884615,
  "evenStrengthShotsAgainst": "22/25",
  "powerPlayShotsAgainst": "1/1",
  "shorthandedShotsAgainst": "0/0",
  "pim": 0
}
```

### Notes
- `name.default` is **abbreviated** (`"J. Eichel"`), not a full name — use the roster endpoint for full names
- `toi` is a `"MM:SS"` string — parse to seconds on ingestion
- Skaters and goalies have **completely different stat shapes** — requires two separate DB tables
- `playerId` is an **integer**

---

## 3. Roster

**`GET /roster/{team_abbrev}/current`**

Full roster for a team. Use this to seed player names before ingesting game stats.

### Key fields

```json
{
  "forwards": [
    {
      "id": 8478427,
      "firstName": { "default": "Sebastian" },
      "lastName": { "default": "Aho" },
      "sweaterNumber": 20,
      "positionCode": "C",
      "shootsCatches": "L",
      "birthDate": "1997-07-26",
      "birthCountry": "FIN",
      "heightInInches": 72,
      "weightInPounds": 189
    }
  ],
  "defense": [...],
  "goalies": [...]
}
```

### Notes
- Returns `forwards`, `defense`, `goalies` as separate arrays — same split as the boxscore
- `id` matches the `playerId` in the boxscore — use this as `external_id`
- Full name is `firstName.default + " " + lastName.default`
- `positionCode`: `"C"`, `"L"`, `"R"`, `"D"`, `"G"`
- Use `/roster/{abbrev}/current` for the active roster; historical seasons use `/roster/{abbrev}/{season}` (e.g. `20242025`)

---

## 4. Player Detail

**`GET /player/{player_id}/landing`**

Full profile for a single player. Use as a fallback if a player appears in a boxscore but isn't in the roster cache.

### Key fields

```json
{
  "playerId": 8478403,
  "firstName": { "default": "Jack" },
  "lastName": { "default": "Eichel" },
  "currentTeamId": 54,
  "currentTeamAbbrev": "VGK",
  "position": "C",
  "sweaterNumber": 9
}
```

---

## Schema implications

| Observation | Schema decision |
|---|---|
| Team `id` is an integer | `Team.external_id = IntegerField` |
| Player `playerId` is an integer | `Player.external_id = IntegerField` |
| Skaters and goalies have different stat fields | Two tables: `SkaterStat`, `GoalieStat` |
| `toi` is a `"MM:SS"` string | Store as `IntegerField` (seconds), parse on ingestion |
| Boxscore has abbreviated names only | Seed players from roster endpoint first |
| `gameState == "OFF"` means final | Filter on this before ingesting stats |
