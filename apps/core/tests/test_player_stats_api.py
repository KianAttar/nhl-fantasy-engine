from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import SkaterStat
from apps.core.tests.helpers import make_game, make_player, make_team


class PlayerStatsAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        team = make_team(1, "TOR")
        away = make_team(2, "BOS")
        cls.player = make_player(team, ext_id=1)
        game = make_game(team, away)
        SkaterStat.objects.create(
            player=cls.player, game=game,
            goals=2, assists=1, fantasy_points=10.0,
        )

    def setUp(self):
        self.client = APIClient()

    def test_returns_200(self):
        self.assertEqual(
            self.client.get(reverse("player-stats", args=[self.player.pk])).status_code, 200,
        )

    def test_returns_404_for_unknown_player(self):
        self.assertEqual(
            self.client.get(reverse("player-stats", args=[9999])).status_code, 404,
        )

    def test_skater_stats_in_response(self):
        data = self.client.get(reverse("player-stats", args=[self.player.pk])).json()
        self.assertEqual(len(data["skater_stats"]), 1)
        self.assertEqual(data["skater_stats"][0]["goals"], 2)
        self.assertEqual(data["skater_stats"][0]["assists"], 1)
