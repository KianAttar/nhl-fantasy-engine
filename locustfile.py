"""
Stress test for the NHL Fantasy Engine API.

Run with web UI:
    uv run locust

Run headless (CI / quick check):
    uv run locust --headless -u 50 -r 10 --run-time 30s --host http://localhost:8000
"""
import random

from locust import HttpUser, between, task

# Dates with actual game data — used for date-filtered leaderboard requests
GAME_DATES = [
    "2026-04-06", "2026-04-07", "2026-04-09", "2026-04-11",
    "2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16",
    "2026-05-01", "2026-05-06", "2026-05-10", "2026-05-14",
    "2026-06-02", "2026-06-04",
]

# A sample of player IDs known to exist in the DB
PLAYER_IDS = [
    2, 10, 17, 18, 19, 20, 21, 22, 23, 24,
    25, 26, 27, 28, 29, 32, 48, 49, 50, 51,
    52, 53, 54, 55, 60, 63, 68, 77, 79, 80,
]


class LeaderboardUser(HttpUser):
    """Simulates a typical API consumer hitting the leaderboard and player endpoints."""

    wait_time = between(0.5, 2)  # seconds between requests per user

    @task(5)
    def leaderboard_all_time(self):
        """All-time leaderboard — most common request, should be cache-hit."""
        self.client.get("/api/leaderboard/", name="/api/leaderboard/ [all-time]")

    @task(3)
    def leaderboard_by_date(self):
        """Date-filtered leaderboard."""
        date = random.choice(GAME_DATES)
        self.client.get(
            f"/api/leaderboard/?date={date}",
            name="/api/leaderboard/ [by-date]",
        )

    @task(2)
    def leaderboard_paginated(self):
        """Large page size — tests serializer throughput."""
        self.client.get(
            "/api/leaderboard/?page_size=200",
            name="/api/leaderboard/ [page_size=200]",
        )

    @task(2)
    def player_stats(self):
        """Per-player stat breakdown."""
        player_id = random.choice(PLAYER_IDS)
        self.client.get(
            f"/api/players/{player_id}/stats/",
            name="/api/players/[id]/stats/",
        )

    @task(1)
    def leaderboard_page_2(self):
        """Pagination — page 2."""
        self.client.get(
            "/api/leaderboard/?page=2",
            name="/api/leaderboard/ [page=2]",
        )
