from apps.core.models import Game, Player, Team


def make_team(ext_id: int, abbrev: str) -> Team:
    return Team.objects.create(external_id=ext_id, abbreviation=abbrev, name=abbrev)


def make_player(team: Team, ext_id: int, pos: str = "C") -> Player:
    return Player.objects.create(
        external_id=ext_id, first_name="Test", last_name=f"Player{ext_id}",
        position=pos, team=team,
    )


def make_game(home: Team, away: Team, ext_id: int = 1, game_date: str = "2026-06-05") -> Game:
    return Game.objects.create(
        external_id=ext_id, home_team=home, away_team=away,
        date=game_date, game_type=2, status=Game.Status.FINAL,
    )
