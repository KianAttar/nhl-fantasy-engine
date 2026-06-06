import logging
from datetime import date, datetime

from celery import chain, chord, group, shared_task

logger = logging.getLogger(__name__)


@shared_task
def nightly_pipeline(date_str: str | None = None) -> None:
    """
    Entry point for Celery beat. Builds the pipeline as a Celery canvas
    and dispatches it — each step runs as its own retryable task.
    """
    target_date = (
        datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    )
    date_str = target_date.strftime("%Y-%m-%d")

    chain(
        ingest_date_task.s(date_str),  # type: ignore
        dispatch_scoring.s(),  # type: ignore
    ).delay()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def ingest_date_task(self, date_str: str) -> dict:
    """
    Pull completed games from the NHL API and write to DB.
    Returns {"date_str": ..., "game_ids": [...]} for the next step.
    """
    from apps.core.models import Game
    from apps.core.services.ingestion import ingest_date
    from apps.core.services.nhl_client import NHLClient

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        client = NHLClient()
        summary = ingest_date(client, target_date)

        game_ids = list(
            Game.objects.filter(date=target_date, status=Game.Status.FINAL).values_list(
                "id", flat=True
            )
        )

        logger.info("Ingested %d games for %s: %s", len(game_ids), date_str, summary)
        return {"date_str": date_str, "game_ids": game_ids}

    except Exception as exc:
        logger.exception("ingest_date_task failed for %s", date_str)
        raise self.retry(exc=exc)


@shared_task
def dispatch_scoring(ingest_result: dict) -> None:
    """
    Fan out scoring as a parallel chord, then refresh cache.
    Receives the dict returned by ingest_date_task via chain.
    """
    game_ids = ingest_result.get("game_ids", [])
    date_str = ingest_result["date_str"]

    if not game_ids:
        logger.info("No final games for %s — skipping scoring", date_str)
        return

    chord(
        group(
            score_skaters_task.si(game_ids),  # type: ignore
            score_goalies_task.si(game_ids),  # type: ignore
        ),
        refresh_cache_task.si(date_str),  # type: ignore
    ).delay()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def score_skaters_task(self, game_ids: list[int]) -> int:
    """Run NumPy scoring for skaters. Retryable independently of goalies."""
    from apps.core.services.scoring import score_skaters

    try:
        count = score_skaters(game_ids)
        logger.info("Scored %d skater rows", count)
        return count
    except Exception as exc:
        logger.exception("score_skaters_task failed for game_ids=%s", game_ids)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def score_goalies_task(self, game_ids: list[int]) -> int:
    """Run NumPy scoring for goalies. Retryable independently of skaters."""
    from apps.core.services.scoring import score_goalies

    try:
        count = score_goalies(game_ids)
        logger.info("Scored %d goalie rows", count)
        return count
    except Exception as exc:
        logger.exception("score_goalies_task failed for game_ids=%s", game_ids)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_cache_task(self, date_str: str) -> None:
    """
    Invalidate and warm the leaderboard cache.
    Fires only after both scoring tasks complete (chord callback).
    """
    from apps.core.services.cache_utils import invalidate_leaderboard, warm_leaderboard

    try:
        invalidate_leaderboard(date_str)
        warm_leaderboard(date_str)
        logger.info("Cache refreshed for %s", date_str)
    except Exception as exc:
        logger.exception("refresh_cache_task failed for %s", date_str)
        raise self.retry(exc=exc)
