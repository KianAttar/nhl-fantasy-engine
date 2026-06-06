from datetime import datetime

from django.core.cache import cache
from django.db.models import FloatField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, Round
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.core.models import Player
from apps.core.serializers import LeaderboardEntrySerializer, PlayerStatsSerializer
from apps.core.services.cache_utils import LEADERBOARD_CACHE_TTL, leaderboard_cache_key


class LeaderboardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class LeaderboardView(ListAPIView):
    """
    GET /api/leaderboard/
    GET /api/leaderboard/?date=2026-06-04

    Returns players ranked by total fantasy points, descending.
    The full ranked list is cached as one entry after each scoring run.
    Pagination slices from the cached list in Python — no DB hit per page.
    """
    serializer_class = LeaderboardEntrySerializer
    pagination_class = LeaderboardPagination

    def list(self, request):  # type: ignore[override]
        date_str = request.GET.get("date")
        cache_key = leaderboard_cache_key(date_str)

        data = cache.get(cache_key)
        if data is None:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data
            cache.set(cache_key, data, timeout=LEADERBOARD_CACHE_TTL)

        page = self.paginate_queryset(data)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(data)

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        date_str = self.request.GET.get("date")

        if date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValidationError({"date": "Use YYYY-MM-DD format."})

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