from datetime import date as date_cls
from unittest.mock import MagicMock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import Game, GoalieStat, Player
from apps.core.services.ingestion import ingest_date
from apps.core.services.scoring import score_goalies, score_skaters


class EndToEndPipelineTests(TestCase):
    """
    Mock the NHL HTTP client, run ingest_date + scoring, assert the leaderboard
    reflects the correct ranked fantasy scores end-to-end.

    Fixture  TOR 3 – BOS 2 (regulation)
      TOR skater : 2G 1A 3S 1H +1 1T  →  13.5 pts
      TOR goalie : W  28sv 2ga        →   8.6 pts
      BOS goalie : L  25sv 3ga        →   2.0 pts
    """

    GAME_DATE = "2026-06-05"
    GAME_ID = 2026010001

    def _mock_client(self) -> MagicMock:
        client = MagicMock()
        client.get_schedule.return_value = {
            "gameWeek": [
                {
                    "date": self.GAME_DATE,
                    "games": [{"id": self.GAME_ID, "gameState": "OFF"}],
                }
            ]
        }
        client.get_boxscore.return_value = {
            "gameDate": f"{self.GAME_DATE}T00:00:00Z",
            "gameType": 2,
            "periodDescriptor": {"periodType": "REG"},
            "awayTeam": {"id": 10, "abbrev": "TOR", "commonName": {"default": "Maple Leafs"}, "score": 3},
            "homeTeam": {"id": 6,  "abbrev": "BOS", "commonName": {"default": "Bruins"},      "score": 2},
            "playerByGameStats": {
                "awayTeam": {
                    "forwards": [
                        {
                            "playerId": 8001, "name": {"default": "TOR Skater"},
                            "position": "C", "goals": 2, "assists": 1, "points": 3,
                            "plusMinus": 1, "pim": 0, "hits": 1, "powerPlayGoals": 0,
                            "sog": 3, "toi": "20:00", "blockedShots": 0,
                            "shifts": 22, "giveaways": 0, "takeaways": 1,
                        }
                    ],
                    "defensemen": [],
                    "goalies": [
                        {
                            "playerId": 8002, "name": {"default": "TOR Goalie"},
                            "starter": True, "decision": "W", "toi": "60:00",
                            "shotsAgainst": 30, "saves": 28, "goalsAgainst": 2,
                            "savePctg": 0.933, "pim": 0,
                        }
                    ],
                },
                "homeTeam": {
                    "forwards": [], "defensemen": [],
                    "goalies": [
                        {
                            "playerId": 8003, "name": {"default": "BOS Goalie"},
                            "starter": True, "decision": "L", "toi": "60:00",
                            "shotsAgainst": 28, "saves": 25, "goalsAgainst": 3,
                            "savePctg": 0.893, "pim": 0,
                        }
                    ],
                },
            },
        }
        return client

    def _run_pipeline(self) -> Game:
        ingest_date(self._mock_client(), date_cls.fromisoformat(self.GAME_DATE))
        game = Game.objects.get(external_id=self.GAME_ID)
        score_skaters([game.id])
        score_goalies([game.id])
        return game

    def test_ingestion_creates_expected_players(self):
        self._run_pipeline()
        self.assertEqual(Player.objects.count(), 3)

    def test_leaderboard_contains_all_scored_players(self):
        self._run_pipeline()
        results = APIClient().get(reverse("leaderboard")).json()["results"]
        self.assertEqual(len(results), 3)

    def test_leaderboard_ordered_by_fantasy_points(self):
        self._run_pipeline()
        results = APIClient().get(reverse("leaderboard")).json()["results"]
        points = [r["total_points"] for r in results]
        self.assertEqual(points, sorted(points, reverse=True))
        self.assertAlmostEqual(points[0], 13.5, places=1)
        self.assertAlmostEqual(points[1], 8.6,  places=1)
        self.assertAlmostEqual(points[2], 2.0,  places=1)

    def test_date_filter_matches_all_time_for_single_game_day(self):
        self._run_pipeline()
        all_time = APIClient().get(reverse("leaderboard")).json()["results"]
        by_date = APIClient().get(
            reverse("leaderboard"), {"date": self.GAME_DATE}
        ).json()["results"]
        self.assertEqual(
            [r["total_points"] for r in all_time],
            [r["total_points"] for r in by_date],
        )
