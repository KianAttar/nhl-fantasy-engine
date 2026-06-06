import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

LEADERBOARD_CACHE_TTL = 60 * 60 * 24  # 24h — invalidated by scoring pipeline before expiry


def leaderboard_cache_key(date_str: str | None) -> str:
    return f"leaderboard:{date_str or 'all'}"


def invalidate_leaderboard(date_str: str | None) -> None:
    """Delete cached leaderboards for the given date and all-time."""
    cache.delete(leaderboard_cache_key(date_str))
    cache.delete(leaderboard_cache_key(None))
    logger.info("Leaderboard cache invalidated for date=%s", date_str or "all")


def warm_leaderboard(date_str: str | None) -> None:
    """
    Pre-populate the leaderboard cache by invoking the view in-process.

    The view caches the full ranked list on first access — one request is
    enough to warm all pages since pagination slices from the cached list.
    We warm both the date-specific and all-time leaderboards.
    """
    try:
        from django.test import RequestFactory

        from apps.core.views import LeaderboardView

        factory = RequestFactory(SERVER_NAME="localhost", SERVER_PORT="8000")
        view = LeaderboardView.as_view()

        if date_str:
            view(factory.get("/api/leaderboard/", {"date": date_str}))
            logger.info("Warmed leaderboard cache for date=%s", date_str)

        view(factory.get("/api/leaderboard/"))
        logger.info("Warmed all-time leaderboard cache")

    except Exception:
        logger.exception("Failed to warm leaderboard cache for date=%s", date_str or "all")