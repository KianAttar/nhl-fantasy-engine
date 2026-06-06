from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import SkaterStat
from apps.core.tests.helpers import make_game, make_player, make_team


class LeaderboardAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        home = make_team(1, "TOR")
        away = make_team(2, "BOS")
        cls.game = make_game(home, away)

        cls.player_a = make_player(home, ext_id=1)  # 12.0 pts
        SkaterStat.objects.create(player=cls.player_a, game=cls.game, fantasy_points=12.0)

        cls.player_b = make_player(away, ext_id=2, pos="D")  # 6.0 pts
        SkaterStat.objects.create(player=cls.player_b, game=cls.game, fantasy_points=6.0)

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_returns_200(self):
        self.assertEqual(self.client.get(reverse("leaderboard")).status_code, 200)

    def test_players_ordered_by_points_descending(self):
        results = self.client.get(reverse("leaderboard")).json()["results"]
        self.assertEqual(results[0]["player_id"], self.player_a.id)
        self.assertEqual(results[1]["player_id"], self.player_b.id)

    def test_player_with_zero_points_excluded(self):
        zero_player = make_player(make_team(3, "MTL"), ext_id=99)
        SkaterStat.objects.create(player=zero_player, game=self.game, fantasy_points=0.0)
        ids = [r["player_id"] for r in self.client.get(reverse("leaderboard")).json()["results"]]
        self.assertNotIn(zero_player.id, ids)

    def test_date_filter_excludes_other_days(self):
        other_team = make_team(3, "MTL")
        other_game = make_game(other_team, other_team, ext_id=2, game_date="2026-06-06")
        visitor = make_player(other_team, ext_id=50)
        SkaterStat.objects.create(player=visitor, game=other_game, fantasy_points=20.0)

        results = self.client.get(reverse("leaderboard"), {"date": "2026-06-05"}).json()["results"]
        ids = [r["player_id"] for r in results]
        self.assertNotIn(visitor.id, ids)
        self.assertIn(self.player_a.id, ids)

    def test_invalid_date_returns_400(self):
        self.assertEqual(
            self.client.get(reverse("leaderboard"), {"date": "not-a-date"}).status_code,
            400,
        )

    def test_pagination_page_size_param(self):
        data = self.client.get(reverse("leaderboard"), {"page_size": 1}).json()
        self.assertEqual(len(data["results"]), 1)
        self.assertIsNotNone(data["next"])

    def test_response_shape(self):
        result = self.client.get(reverse("leaderboard")).json()["results"][0]
        for field in ("player_id", "total_points", "team", "position"):
            self.assertIn(field, result)
