from django.db import models


class Team(models.Model):
    # external_id is the NHL API's integer team ID (e.g. 12 for CAR, 54 for VGK)
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)        # "Carolina Hurricanes"
    abbreviation = models.CharField(max_length=10) # "CAR"

    def __str__(self):
        return self.abbreviation


class Player(models.Model):
    class Position(models.TextChoices):
        CENTRE     = "C", "Centre"
        LEFT_WING  = "L", "Left Wing"
        RIGHT_WING = "R", "Right Wing"
        DEFENSE    = "D", "Defense"
        GOALIE     = "G", "Goalie"

    external_id = models.IntegerField(unique=True)  # NHL API playerId integer
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name="players")
    position = models.CharField(max_length=2, choices=Position.choices)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Game(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE      = "live",      "Live"
        FINAL     = "final",     "Final"

    external_id = models.IntegerField(unique=True)  # NHL API game ID integer
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_games")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_games")
    date = models.DateField()
    game_type = models.IntegerField()  # 2 = regular season, 3 = playoffs
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)

    class Meta:
        indexes = [
            models.Index(fields=["date", "status"]),
        ]

    def __str__(self):
        return f"{self.away_team} @ {self.home_team} ({self.date})"


class SkaterStat(models.Model):
    """Per-game stats for forwards and defense men."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="skater_stats")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="skater_stats")
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    plus_minus = models.IntegerField(default=0)
    pim = models.IntegerField(default=0)            # penalty minutes
    hits = models.IntegerField(default=0)
    power_play_goals = models.IntegerField(default=0)
    shots = models.IntegerField(default=0)          # shots on goal
    faceoff_pct = models.FloatField(null=True, blank=True)
    toi = models.IntegerField(default=0)            # time on ice in seconds
    blocked_shots = models.IntegerField(default=0)
    shifts = models.IntegerField(default=0)
    giveaways = models.IntegerField(default=0)
    takeaways = models.IntegerField(default=0)
    fantasy_points = models.FloatField(default=0.0, db_index=True)  # calculated by scoring engine

    class Meta:
        unique_together = [("player", "game")]  # prevents duplicate ingestion
        indexes = [
            models.Index(fields=["game"]),
            models.Index(fields=["player", "fantasy_points"]),
        ]

    def __str__(self):
        return f"{self.player} — {self.game}"


class GoalieStat(models.Model):
    """Per-game stats for goalies — completely different shape from skaters."""

    class Decision(models.TextChoices):
        WIN     = "W", "Win"
        LOSS    = "L", "Loss"
        OT_LOSS = "O", "OT Loss"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="goalie_stats")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="goalie_stats")
    starter = models.BooleanField(default=False)
    decision = models.CharField(max_length=1, choices=Decision.choices, null=True, blank=True)
    toi = models.IntegerField(default=0)            # seconds
    shots_against = models.IntegerField(default=0)
    saves = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    save_pct = models.FloatField(null=True, blank=True)
    pim = models.IntegerField(default=0)
    fantasy_points = models.FloatField(default=0.0, db_index=True)

    class Meta:
        unique_together = [("player", "game")]
        indexes = [
            models.Index(fields=["game"]),
        ]

    def __str__(self):
        return f"{self.player} (G) — {self.game}"


class SkaterScoringRule(models.Model):
    """Fantasy point weight for a skater stat. Stored in DB so scoring can change without a deploy."""

    class StatName(models.TextChoices):
        GOALS            = "goals",            "Goals"
        ASSISTS          = "assists",          "Assists"
        SHOTS            = "shots",            "Shots on Goal"
        HITS             = "hits",             "Hits"
        PLUS_MINUS       = "plus_minus",       "Plus/Minus"
        PIM              = "pim",              "Penalty Minutes"
        POWER_PLAY_GOALS = "power_play_goals", "Power Play Goals"
        BLOCKED_SHOTS    = "blocked_shots",    "Blocked Shots"
        TAKEAWAYS        = "takeaways",        "Takeaways"
        GIVEAWAYS        = "giveaways",        "Giveaways"

    stat_name = models.CharField(max_length=50, choices=StatName.choices, unique=True)
    points_per_unit = models.FloatField()

    def __str__(self):
        return f"skater.{self.stat_name} = {self.points_per_unit}pts"


class PipelineControl(models.Model):
    """No DB table — exists solely to anchor the Pipeline Control admin page."""
    class Meta:
        managed = False
        verbose_name = "Pipeline Control"
        verbose_name_plural = "Pipeline Control"


class GoalieScoringRule(models.Model):
    """Fantasy point weight for a goalie stat. Stored in DB so scoring can change without a deploy."""

    class StatName(models.TextChoices):
        SAVES         = "saves",         "Saves"
        GOALS_AGAINST = "goals_against", "Goals Against"
        SHOTS_AGAINST = "shots_against", "Shots Against"
        WIN           = "win",           "Win"
        OT_LOSS       = "ot_loss",       "OT Loss"

    stat_name = models.CharField(max_length=50, choices=StatName.choices, unique=True)
    points_per_unit = models.FloatField()

    def __str__(self):
        return f"goalie.{self.stat_name} = {self.points_per_unit}pts"
