from datetime import datetime

from django.db.models import FloatField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, Round
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import CursorPagination

from apps.core.models import Player
from apps.core.serializers import LeaderboardEntrySerializer, PlayerStatsSerializer


class LeaderboardPagination(CursorPagination):
    # Cursor pagination needs a stable ordering. We order by total_points
    # descending, then id ascending as a tiebreaker so the cursor position
    # is always unambiguous.
    ordering = ("-total_points", "id")
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class LeaderboardView(ListAPIView):
    """
    GET /api/leaderboard/
    GET /api/leaderboard/?date=2026-06-04

    Returns players ranked by total fantasy points, descending.
    Filters to a single date when ?date= is provided, otherwise aggregates all time.
    """
    serializer_class = LeaderboardEntrySerializer
    pagination_class = LeaderboardPagination

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        date_str = self.request.GET.get("date")

        if date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValidationError({"date": "Use YYYY-MM-DD format."})

        # Annotate each Player with the sum of fantasy points across all their
        # stat rows. Coalesce turns NULL (no stats) into 0.0.
        # Since every player is either a skater or a goalie, only one of the
        # two sums will be non-zero — adding them gives the correct total.
        date_filter_skater = Q(skater_stats__game__date=date_str) if date_str else Q()
        date_filter_goalie = Q(goalie_stats__game__date=date_str) if date_str else Q()

        skater_pts = Coalesce(
            Sum("skater_stats__fantasy_points", filter=date_filter_skater),
            0.0,
            output_field=FloatField(),
        )
        goalie_pts = Coalesce(
            Sum("goalie_stats__fantasy_points", filter=date_filter_goalie),
            0.0,
            output_field=FloatField(),
        )

        return (
            Player.objects.select_related("team")
            .annotate(total_points=Round(skater_pts + goalie_pts, 2))
            .filter(total_points__gt=0)
            .order_by("-total_points", "id")
        )


class PlayerStatsView(RetrieveAPIView):
    """
    GET /api/players/{id}/stats/

    Returns a player's full profile with all their game-by-game stats.
    """
    serializer_class = PlayerStatsSerializer

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        return Player.objects.select_related("team").prefetch_related(
            "skater_stats__game__home_team",
            "skater_stats__game__away_team",
            "goalie_stats__game__home_team",
            "goalie_stats__game__away_team",
        )
