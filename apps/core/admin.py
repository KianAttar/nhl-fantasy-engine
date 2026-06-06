from django.contrib import admin

from apps.core.models import (
    Game,
    GoalieScoringRule,
    GoalieStat,
    Player,
    SkaterScoringRule,
    SkaterStat,
    Team,
)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("abbreviation", "name", "external_id")
    search_fields = ("abbreviation", "name")
    ordering = ("abbreviation",)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "position", "team")
    list_filter = ("position", "team")
    search_fields = ("first_name", "last_name")


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("__str__", "date", "status", "game_type")
    list_filter = ("status", "game_type")
    ordering = ("-date",)


@admin.register(SkaterStat)
class SkaterStatAdmin(admin.ModelAdmin):
    list_display = ("player", "game", "goals", "assists", "shots", "fantasy_points")
    list_filter = ("game__date",)
    ordering = ("-fantasy_points",)


@admin.register(GoalieStat)
class GoalieStatAdmin(admin.ModelAdmin):
    list_display = ("player", "game", "decision", "saves", "goals_against", "fantasy_points")
    list_filter = ("decision",)
    ordering = ("-fantasy_points",)


@admin.register(SkaterScoringRule)
class SkaterScoringRuleAdmin(admin.ModelAdmin):
    list_display = ("stat_name", "points_per_unit")


@admin.register(GoalieScoringRule)
class GoalieScoringRuleAdmin(admin.ModelAdmin):
    list_display = ("stat_name", "points_per_unit")
