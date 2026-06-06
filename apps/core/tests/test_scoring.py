from django.test import TestCase

from apps.core.models import GoalieStat, SkaterStat
from apps.core.services.scoring import score_goalies, score_skaters
from apps.core.tests.helpers import make_game, make_player, make_team


class ScoreSkaterTests(TestCase):
    def setUp(self):
        home = make_team(1, "TOR")
        away = make_team(2, "BOS")
        self.player = make_player(home, ext_id=1)
        self.game = make_game(home, away)

    def test_known_stats_produce_correct_points(self):
        # goals=2*4 + assists=1*2 + shots=3*0.5 + hits=2*0.5 + plus_minus=1*1
        # + ppg=1*1 + blocked=1*0.5 + takeaways=1*0.5 = 15.5
        stat = SkaterStat.objects.create(
            player=self.player, game=self.game,
            goals=2, assists=1, shots=3, hits=2,
            plus_minus=1, pim=0, power_play_goals=1,
            blocked_shots=1, takeaways=1, giveaways=0,
        )
        score_skaters([self.game.id])
        stat.refresh_from_db()
        self.assertAlmostEqual(stat.fantasy_points, 15.5, places=2)

    def test_giveaways_subtract_points(self):
        # goals=1 → +4.0, giveaways=2 → -1.0  |  total = 3.0
        stat = SkaterStat.objects.create(
            player=self.player, game=self.game, goals=1, giveaways=2,
        )
        score_skaters([self.game.id])
        stat.refresh_from_db()
        self.assertAlmostEqual(stat.fantasy_points, 3.0, places=2)

    def test_zero_stats_produce_zero_points(self):
        stat = SkaterStat.objects.create(player=self.player, game=self.game)
        score_skaters([self.game.id])
        stat.refresh_from_db()
        self.assertEqual(stat.fantasy_points, 0.0)

    def test_returns_row_count(self):
        other = make_player(make_team(3, "MTL"), ext_id=2)
        SkaterStat.objects.create(player=self.player, game=self.game, goals=1)
        SkaterStat.objects.create(player=other, game=self.game, goals=1)
        self.assertEqual(score_skaters([self.game.id]), 2)

    def test_game_id_filter_skips_other_games(self):
        other_team = make_team(3, "MTL")
        other_game = make_game(other_team, other_team, ext_id=2, game_date="2026-06-06")
        stat = SkaterStat.objects.create(
            player=make_player(other_team, ext_id=2), game=other_game, goals=5,
        )
        score_skaters([self.game.id])
        stat.refresh_from_db()
        self.assertEqual(stat.fantasy_points, 0.0)


class ScoreGoalieTests(TestCase):
    def setUp(self):
        home = make_team(1, "TOR")
        away = make_team(2, "BOS")
        self.player = make_player(home, ext_id=10, pos="G")
        self.game = make_game(home, away)

    def test_win_produces_correct_points(self):
        # 30*0.2 + 2*(-1) + 32*0 + 1*5 + 0*1 = 6 - 2 + 5 = 9.0
        stat = GoalieStat.objects.create(
            player=self.player, game=self.game,
            saves=30, goals_against=2, shots_against=32,
            decision=GoalieStat.Decision.WIN,
        )
        score_goalies([self.game.id])
        stat.refresh_from_db()
        self.assertAlmostEqual(stat.fantasy_points, 9.0, places=2)

    def test_ot_loss_produces_correct_points(self):
        # 28*0.2 + 3*(-1) + 31*0 + 0*5 + 1*1 = 5.6 - 3 + 1 = 3.6
        stat = GoalieStat.objects.create(
            player=self.player, game=self.game,
            saves=28, goals_against=3, shots_against=31,
            decision=GoalieStat.Decision.OT_LOSS,
        )
        score_goalies([self.game.id])
        stat.refresh_from_db()
        self.assertAlmostEqual(stat.fantasy_points, 3.6, places=2)

    def test_loss_gets_no_win_or_ot_bonus(self):
        # 25*0.2 + 4*(-1) + 29*0 + 0*5 + 0*1 = 5 - 4 = 1.0
        stat = GoalieStat.objects.create(
            player=self.player, game=self.game,
            saves=25, goals_against=4, shots_against=29,
            decision=GoalieStat.Decision.LOSS,
        )
        score_goalies([self.game.id])
        stat.refresh_from_db()
        self.assertAlmostEqual(stat.fantasy_points, 1.0, places=2)

    def test_returns_row_count(self):
        other = make_player(make_team(3, "MTL"), ext_id=11, pos="G")
        GoalieStat.objects.create(
            player=self.player, game=self.game, saves=25, decision=GoalieStat.Decision.WIN,
        )
        GoalieStat.objects.create(
            player=other, game=self.game, saves=20, decision=GoalieStat.Decision.LOSS,
        )
        self.assertEqual(score_goalies([self.game.id]), 2)
