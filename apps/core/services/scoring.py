import logging

import numpy as np

from apps.core.models import GoalieScoringRule, GoalieStat, SkaterScoringRule, SkaterStat

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# Ordered list of stat field names that map to SkaterScoringRule.StatName values.
# The order here defines the column order in the NumPy matrix — it must stay
# consistent between where we build the matrix and where we build the weights vector.
SKATER_STAT_FIELDS = [
    "goals",
    "assists",
    "shots",
    "hits",
    "plus_minus",
    "pim",
    "power_play_goals",
    "blocked_shots",
    "takeaways",
    "giveaways",
]

# Goalie stat columns. win and ot_loss are not DB columns — they are derived
# from the decision field as 1.0/0.0 binary values when building the matrix.
GOALIE_STAT_FIELDS = [
    "saves",
    "goals_against",
    "shots_against",
    "win",
    "ot_loss",
]


def _build_skater_weights() -> np.ndarray:
    """
    Load SkaterScoringRule rows and return a weights vector aligned to SKATER_STAT_FIELDS.
    Missing rules default to 0.0 (stat doesn't count toward fantasy points).
    """
    rules = dict(SkaterScoringRule.objects.values_list("stat_name", "points_per_unit"))
    return np.array([rules.get(field, 0.0) for field in SKATER_STAT_FIELDS], dtype=np.float64)


def _build_goalie_weights() -> np.ndarray:
    """Load GoalieScoringRule rows and return a weights vector aligned to GOALIE_STAT_FIELDS."""
    rules = dict(GoalieScoringRule.objects.values_list("stat_name", "points_per_unit"))
    return np.array([rules.get(field, 0.0) for field in GOALIE_STAT_FIELDS], dtype=np.float64)


def score_skaters(game_ids: list[int] | None = None) -> int:
    """
    Calculate and write fantasy_points for all SkaterStat rows.
    Optionally filter to specific game IDs (e.g. just last night's games).
    Processes rows in cursor-paginated batches of BATCH_SIZE.
    Returns total rows updated.
    """
    weights = _build_skater_weights()

    qs = SkaterStat.objects.order_by("id")
    if game_ids:
        qs = qs.filter(game_id__in=game_ids)

    total_updated = 0
    last_id = 0

    while True:
        batch = list(
            qs.filter(id__gt=last_id)
            .values("id", *SKATER_STAT_FIELDS)
            [:BATCH_SIZE]
        )
        if not batch:
            break

        # Build matrix: each row is one stat row, columns match SKATER_STAT_FIELDS order
        matrix = np.array(
            [[row[field] for field in SKATER_STAT_FIELDS] for row in batch],
            dtype=np.float64,
        )

        # Matrix-vector multiply: (n × 10) @ (10,) → (n,)
        points = matrix @ weights

        # Write results back — bulk_update sends a single UPDATE with CASE WHEN
        stat_objs = [
            SkaterStat(id=row["id"], fantasy_points=float(pts))
            for row, pts in zip(batch, points)
        ]
        SkaterStat.objects.bulk_update(stat_objs, ["fantasy_points"])

        total_updated += len(batch)
        last_id = batch[-1]["id"]
        logger.debug("Scored skater batch up to id=%d (%d total)", last_id, total_updated)

    return total_updated


def score_goalies(game_ids: list[int] | None = None) -> int:
    """
    Calculate and write fantasy_points for all GoalieStat rows.
    win and ot_loss are encoded as binary columns (1.0/0.0) derived from the
    decision field during matrix construction, so points = matrix @ weights
    is the complete calculation with no post-processing.
    Returns total rows updated.
    """
    weights = _build_goalie_weights()

    # Fetch only the DB columns — win/ot_loss are derived, not fetched
    db_fields = ["saves", "goals_against", "shots_against"]

    qs = GoalieStat.objects.order_by("id")
    if game_ids:
        qs = qs.filter(game_id__in=game_ids)

    total_updated = 0
    last_id = 0

    while True:
        batch = list(
            qs.filter(id__gt=last_id)
            .values("id", "decision", *db_fields)
            [:BATCH_SIZE]
        )
        if not batch:
            break

        # Build matrix: numeric DB columns + binary win/ot_loss columns derived from decision
        matrix = np.array(
            [
                [
                    row["saves"],
                    row["goals_against"],
                    row["shots_against"],
                    1.0 if row["decision"] == GoalieStat.Decision.WIN else 0.0,
                    1.0 if row["decision"] == GoalieStat.Decision.OT_LOSS else 0.0,
                ]
                for row in batch
            ],
            dtype=np.float64,
        )

        points = matrix @ weights

        stat_objs = [
            GoalieStat(id=row["id"], fantasy_points=float(pts))
            for row, pts in zip(batch, points)
        ]
        GoalieStat.objects.bulk_update(stat_objs, ["fantasy_points"])

        total_updated += len(batch)
        last_id = batch[-1]["id"]
        logger.debug("Scored goalie batch up to id=%d (%d total)", last_id, total_updated)

    return total_updated
