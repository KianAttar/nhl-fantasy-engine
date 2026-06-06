import logging
from datetime import date

from django.core.cache import cache

from apps.core.models import Game, GoalieStat, Player, SkaterStat, Team
from apps.core.services.nhl_client import NHLClient, NHL_TEAMS

logger = logging.getLogger(__name__)


def parse_toi(toi_str: str) -> int:
    """Convert 'MM:SS' string from the NHL API into total seconds."""
    if not toi_str or toi_str == "00:00":
        return 0
    parts = toi_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def seed_rosters(client: NHLClient) -> tuple[int, int]:
    """
    Pull every team's roster from the NHL API and upsert Player rows.
    Returns (teams_count, players_count).
    """
    total_players = 0

    for abbrev in NHL_TEAMS:
        try:
            data = client.get_roster(abbrev)
        except Exception:
            logger.warning("Failed to fetch roster for %s, skipping", abbrev)
            continue

        all_positions = (
            data.get("forwards", [])
            + data.get("defensemen", [])
            + data.get("goalies", [])
        )

        for p in all_positions:
            Player.objects.update_or_create(
                external_id=p["id"],
                defaults={
                    "first_name": p.get("firstName", {}).get("default", ""),
                    "last_name": p.get("lastName", {}).get("default", ""),
                    "position": p.get("positionCode", "C"),
                },
            )
            total_players += 1

    return len(NHL_TEAMS), total_players


def ingest_date(client: NHLClient, target_date: date) -> dict:
    """
    Ingest all completed games for a given date.
    Returns a summary dict of what was created/updated.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    schedule = client.get_schedule(date_str)

    # The schedule response wraps games under gameWeek[0].games
    game_days = schedule.get("gameWeek", [])
    if not game_days:
        return {"games": 0, "skater_stats": 0, "goalie_stats": 0}

    # Find the day matching our date (the API sometimes returns surrounding days)
    games_list = []
    for day in game_days:
        if day.get("date") == date_str:
            games_list = day.get("games", [])
            break

    completed = [g for g in games_list if g.get("gameState") == "OFF"]
    logger.info("%d completed games found for %s", len(completed), date_str)

    total_skater_stats = 0
    total_goalie_stats = 0

    for game_summary in completed:
        game_id = game_summary["id"]
        try:
            skater_count, goalie_count = _ingest_game(client, game_summary)
            total_skater_stats += skater_count
            total_goalie_stats += goalie_count
        except Exception:
            logger.exception("Failed to ingest game %d", game_id)

    # Invalidate leaderboard cache for this date and all-time so next request
    # reflects the newly ingested data.
    cache.delete(f"leaderboard:{date_str}")
    cache.delete("leaderboard:all")

    return {
        "games": len(completed),
        "skater_stats": total_skater_stats,
        "goalie_stats": total_goalie_stats,
    }


def _ingest_game(client: NHLClient, game_summary: dict) -> tuple[int, int]:
    """Ingest a single game. Returns (skater_stat_count, goalie_stat_count)."""
    game_id = game_summary["id"]
    boxscore = client.get_boxscore(game_id)

    # --- Upsert teams ---
    away_raw = boxscore["awayTeam"]
    home_raw = boxscore["homeTeam"]

    away_team, _ = Team.objects.update_or_create(
        external_id=away_raw["id"],
        defaults={
            "name": away_raw.get("commonName", {}).get("default", away_raw["abbrev"]),
            "abbreviation": away_raw["abbrev"],
        },
    )
    home_team, _ = Team.objects.update_or_create(
        external_id=home_raw["id"],
        defaults={
            "name": home_raw.get("commonName", {}).get("default", home_raw["abbrev"]),
            "abbreviation": home_raw["abbrev"],
        },
    )

    # --- Upsert game ---
    # Determine if the game went to OT — needed for goalie OT-loss detection
    period_type = boxscore.get("periodDescriptor", {}).get("periodType", "REG")
    went_to_ot = period_type == "OT"

    game_date = boxscore.get("gameDate", "")[:10]  # "2026-06-04T..." → "2026-06-04"

    game, _ = Game.objects.update_or_create(
        external_id=game_id,
        defaults={
            "home_team": home_team,
            "away_team": away_team,
            "date": game_date,
            "game_type": boxscore.get("gameType", 2),
            "home_score": home_raw.get("score"),
            "away_score": away_raw.get("score"),
            "status": Game.Status.FINAL,
        },
    )

    # --- Upsert player stats ---
    player_stats = boxscore.get("playerByGameStats", {})
    skater_objs = []
    goalie_objs = []

    for side in ("awayTeam", "homeTeam"):
        team_obj = away_team if side == "awayTeam" else home_team
        side_stats = player_stats.get(side, {})

        # Skaters: forwards + defensemen
        for player_raw in side_stats.get("forwards", []) + side_stats.get("defensemen", []):
            stat = _build_skater_stat(player_raw, game, team_obj)
            if stat:
                skater_objs.append(stat)

        # Goalies
        for player_raw in side_stats.get("goalies", []):
            stat = _build_goalie_stat(player_raw, game, team_obj, went_to_ot)
            if stat:
                goalie_objs.append(stat)

    # bulk_create with update_conflicts=True → single SQL INSERT ... ON CONFLICT DO UPDATE
    # update_fields lists every column except the unique constraint columns (player, game)
    SkaterStat.objects.bulk_create(
        skater_objs,
        update_conflicts=True,
        unique_fields=["player", "game"],
        update_fields=[
            "goals", "assists", "points", "plus_minus", "pim", "hits",
            "power_play_goals", "shots", "faceoff_pct", "toi",
            "blocked_shots", "shifts", "giveaways", "takeaways",
        ],
    )
    GoalieStat.objects.bulk_create(
        goalie_objs,
        update_conflicts=True,
        unique_fields=["player", "game"],
        update_fields=[
            "starter", "decision", "toi", "shots_against", "saves",
            "goals_against", "save_pct", "pim",
        ],
    )

    return len(skater_objs), len(goalie_objs)


def _get_or_stub_player(player_id: int, name_default: str, position: str, team: Team) -> Player:
    """
    Return an existing Player or create a stub.

    If seed_rosters was run first the player exists with a full name.
    If not (e.g. in tests), we create a minimal stub using the abbreviated
    name from the boxscore so ingestion doesn't crash.
    """
    player, _ = Player.objects.update_or_create(
        external_id=player_id,
        defaults={
            "first_name": name_default,
            "last_name": "",
            "position": position,
            "team": team,
        },
    )
    return player


def _build_skater_stat(raw: dict, game: Game, team: Team) -> SkaterStat | None:
    player_id = raw.get("playerId")
    if not player_id:
        return None

    player = _get_or_stub_player(
        player_id,
        raw.get("name", {}).get("default", ""),
        raw.get("position", "C"),
        team,
    )

    faceoff_raw = raw.get("faceoffWinningPctg")
    faceoff_pct = float(faceoff_raw) if faceoff_raw is not None and faceoff_raw != 0.0 else None

    return SkaterStat(
        player=player,
        game=game,
        goals=raw.get("goals", 0),
        assists=raw.get("assists", 0),
        points=raw.get("points", 0),
        plus_minus=raw.get("plusMinus", 0),
        pim=raw.get("pim", 0),
        hits=raw.get("hits", 0),
        power_play_goals=raw.get("powerPlayGoals", 0),
        shots=raw.get("sog", 0),
        faceoff_pct=faceoff_pct,
        toi=parse_toi(raw.get("toi", "0:00")),
        blocked_shots=raw.get("blockedShots", 0),
        shifts=raw.get("shifts", 0),
        giveaways=raw.get("giveaways", 0),
        takeaways=raw.get("takeaways", 0),
    )


def _build_goalie_stat(raw: dict, game: Game, team: Team, went_to_ot: bool) -> GoalieStat | None:
    player_id = raw.get("playerId")
    if not player_id:
        return None

    player = _get_or_stub_player(
        player_id,
        raw.get("name", {}).get("default", ""),
        "G",
        team,
    )

    # Translate API decision string → our Decision enum
    # "W" stays "W", "L" becomes "O" if the game went to OT, otherwise stays "L"
    api_decision = raw.get("decision")
    if api_decision == "L" and went_to_ot:
        decision = GoalieStat.Decision.OT_LOSS
    elif api_decision == "W":
        decision = GoalieStat.Decision.WIN
    elif api_decision == "L":
        decision = GoalieStat.Decision.LOSS
    else:
        decision = None  # backup goalie who didn't play long enough to get a decision

    save_pct_raw = raw.get("savePctg")

    return GoalieStat(
        player=player,
        game=game,
        starter=raw.get("starter", False),
        decision=decision,
        toi=parse_toi(raw.get("toi", "0:00")),
        shots_against=raw.get("shotsAgainst", 0),
        saves=raw.get("saves", 0),
        goals_against=raw.get("goalsAgainst", 0),
        save_pct=float(save_pct_raw) if save_pct_raw is not None else None,
        pim=raw.get("pim", 0),
    )
