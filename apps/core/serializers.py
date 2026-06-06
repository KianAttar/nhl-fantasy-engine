from rest_framework import serializers

from apps.core.models import Game, GoalieStat, Player, SkaterStat


class LeaderboardEntrySerializer(serializers.Serializer):
    """One row in the leaderboard — a player with their aggregated fantasy points."""
    player_id = serializers.IntegerField(source="id")
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    position = serializers.CharField()
    team = serializers.StringRelatedField()   # calls Team.__str__() → abbreviation
    total_points = serializers.FloatField()


class GameSerializer(serializers.ModelSerializer):
    home_team = serializers.StringRelatedField()
    away_team = serializers.StringRelatedField()

    class Meta:
        model = Game
        fields = ["id", "date", "home_team", "away_team", "home_score", "away_score", "status"]


class SkaterStatSerializer(serializers.ModelSerializer):
    game = GameSerializer()

    class Meta:
        model = SkaterStat
        fields = [
            "game", "goals", "assists", "points", "plus_minus", "pim",
            "hits", "power_play_goals", "shots", "blocked_shots",
            "takeaways", "giveaways", "toi", "fantasy_points",
        ]


class GoalieStatSerializer(serializers.ModelSerializer):
    game = GameSerializer()

    class Meta:
        model = GoalieStat
        fields = [
            "game", "starter", "decision", "saves", "shots_against",
            "goals_against", "save_pct", "toi", "fantasy_points",
        ]


class PlayerStatsSerializer(serializers.ModelSerializer):
    """Player detail with their full game-by-game stat history."""
    team = serializers.StringRelatedField()
    skater_stats = SkaterStatSerializer(many=True)
    goalie_stats = GoalieStatSerializer(many=True)

    class Meta:
        model = Player
        fields = [
            "id", "first_name", "last_name", "position", "team",
            "skater_stats", "goalie_stats",
        ]
