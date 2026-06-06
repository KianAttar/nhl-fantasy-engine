from django.urls import path

from apps.core.views import LeaderboardView, PlayerStatsView

urlpatterns = [
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("players/<int:pk>/stats/", PlayerStatsView.as_view(), name="player-stats"),
]
