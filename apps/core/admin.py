import datetime

from django.contrib import admin, messages
from django.template.response import TemplateResponse

from apps.core.models import (
    Game,
    GoalieScoringRule,
    GoalieStat,
    PipelineControl,
    Player,
    SkaterScoringRule,
    SkaterStat,
    Team,
)

admin.site.site_header = "NHL Fantasy Engine"
admin.site.site_title = "NHL Fantasy Admin"
admin.site.index_title = "Control Panel"


# ── Teams ─────────────────────────────────────────────────────────────────────

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("abbreviation", "name", "external_id", "player_count")
    search_fields = ("abbreviation", "name")
    ordering = ("abbreviation",)

    @admin.display(description="Players")
    def player_count(self, obj):
        return obj.players.count()


# ── Players ───────────────────────────────────────────────────────────────────

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "position", "team")
    list_filter = ("position", "team")
    search_fields = ("first_name", "last_name")
    ordering = ("last_name",)


# ── Games ─────────────────────────────────────────────────────────────────────

@admin.action(description="Re-ingest selected games from NHL API")
def reingest_games(modeladmin, request, queryset):
    from apps.core.tasks import ingest_date_task
    dates = set(queryset.values_list("date", flat=True))
    for d in dates:
        ingest_date_task.delay(d.strftime("%Y-%m-%d"))
    modeladmin.message_user(request, f"Re-ingestion queued for {len(dates)} date(s).")


@admin.action(description="Re-score selected games")
def rescore_games(modeladmin, request, queryset):
    from celery import chord, group

    from apps.core.tasks import refresh_cache_task, score_goalies_task, score_skaters_task

    dates = set(queryset.values_list("date", flat=True))
    for d in dates:
        date_str = d.strftime("%Y-%m-%d")
        game_ids = list(queryset.filter(date=d).values_list("id", flat=True))
        chord(
            group(score_skaters_task.si(game_ids), score_goalies_task.si(game_ids)),
            refresh_cache_task.si(date_str),
        ).delay()
    modeladmin.message_user(request, f"Re-scoring queued for {queryset.count()} game(s).")


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("__str__", "date", "status", "game_type", "home_score", "away_score")
    list_filter = ("status", "game_type")
    search_fields = ("home_team__abbreviation", "away_team__abbreviation")
    ordering = ("-date",)
    date_hierarchy = "date"
    actions = [reingest_games, rescore_games]


# ── Stats ─────────────────────────────────────────────────────────────────────

@admin.register(SkaterStat)
class SkaterStatAdmin(admin.ModelAdmin):
    list_display = ("player", "game_date", "opponent", "goals", "assists", "shots", "hits", "fantasy_points")
    list_filter = ("game__date",)
    search_fields = ("player__first_name", "player__last_name")
    ordering = ("-fantasy_points",)
    date_hierarchy = "game__date"

    @admin.display(description="Date", ordering="game__date")
    def game_date(self, obj):
        return obj.game.date

    @admin.display(description="Opponent")
    def opponent(self, obj):
        return str(obj.game)


@admin.register(GoalieStat)
class GoalieStatAdmin(admin.ModelAdmin):
    list_display = ("player", "game_date", "decision", "saves", "goals_against", "save_pct", "fantasy_points")
    list_filter = ("decision", "game__date")
    search_fields = ("player__first_name", "player__last_name")
    ordering = ("-fantasy_points",)
    date_hierarchy = "game__date"

    @admin.display(description="Date", ordering="game__date")
    def game_date(self, obj):
        return obj.game.date


# ── Scoring rules ─────────────────────────────────────────────────────────────

@admin.register(SkaterScoringRule)
class SkaterScoringRuleAdmin(admin.ModelAdmin):
    list_display = ("stat_name", "points_per_unit")
    ordering = ("stat_name",)


@admin.register(GoalieScoringRule)
class GoalieScoringRuleAdmin(admin.ModelAdmin):
    list_display = ("stat_name", "points_per_unit")
    ordering = ("stat_name",)


# ── Pipeline Control ──────────────────────────────────────────────────────────

@admin.register(PipelineControl)
class PipelineControlAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST":
            self._handle_post(request)

        recent_tasks = []
        try:
            from django_celery_results.models import TaskResult
            recent_tasks = TaskResult.objects.order_by("-date_done")[:20]
        except Exception:
            pass

        context = {
            **self.admin_site.each_context(request),
            "title": "Pipeline Control",
            "opts": self.model._meta,
            "today": datetime.date.today().isoformat(),
            "stats": self._db_stats(),
            "recent_tasks": recent_tasks,
        }
        return TemplateResponse(request, "admin/core/pipeline_control.html", context)

    def _handle_post(self, request):
        action = request.POST.get("action")
        date_str = request.POST.get("date")

        if not date_str:
            self.message_user(request, "Please select a date.", level=messages.ERROR)
            return

        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self.message_user(request, "Invalid date format.", level=messages.ERROR)
            return

        if action == "ingest":
            from apps.core.tasks import ingest_date_task
            ingest_date_task.delay(date_str)
            self.message_user(request, f"Ingestion task queued for {date_str}.")

        elif action == "score":
            from celery import chord, group

            from apps.core.tasks import refresh_cache_task, score_goalies_task, score_skaters_task

            game_ids = list(
                Game.objects.filter(date=date_str, status=Game.Status.FINAL)
                .values_list("id", flat=True)
            )
            if not game_ids:
                self.message_user(
                    request,
                    f"No final games found for {date_str}. Run Ingest first.",
                    level=messages.WARNING,
                )
                return
            chord(
                group(score_skaters_task.si(game_ids), score_goalies_task.si(game_ids)),
                refresh_cache_task.si(date_str),
            ).delay()
            self.message_user(request, f"Scoring queued for {date_str} ({len(game_ids)} games).")

        elif action == "full_pipeline":
            from apps.core.tasks import nightly_pipeline
            nightly_pipeline.delay(date_str)
            self.message_user(request, f"Full pipeline queued for {date_str}.")

    @staticmethod
    def _db_stats() -> dict:
        return {
            "teams": Team.objects.count(),
            "players": Player.objects.count(),
            "games": Game.objects.count(),
            "games_final": Game.objects.filter(status=Game.Status.FINAL).count(),
            "skater_stats": SkaterStat.objects.count(),
            "goalie_stats": GoalieStat.objects.count(),
            "last_game_date": (
                Game.objects.filter(status=Game.Status.FINAL)
                .order_by("-date")
                .values_list("date", flat=True)
                .first()
            ),
        }
