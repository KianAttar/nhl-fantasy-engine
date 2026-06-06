from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Game
from apps.core.services.cache_utils import invalidate_leaderboard, warm_leaderboard
from apps.core.services.scoring import score_goalies, score_skaters


class Command(BaseCommand):
    help = "Calculate fantasy points for ingested stats using the NumPy scoring engine."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Only score games on this date (YYYY-MM-DD). Omit to score all unscored rows.",
        )

    def handle(self, *args, **options):
        game_ids = None

        if options["date"]:
            try:
                target_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError(f"Invalid date format: '{options['date']}'. Use YYYY-MM-DD.")

            game_ids = list(
                Game.objects.filter(date=target_date, status=Game.Status.FINAL)
                .values_list("id", flat=True)
            )
            if not game_ids:
                self.stdout.write(self.style.WARNING(f"No final games found for {target_date}."))
                return

        self.stdout.write("Scoring skaters...")
        skater_count = score_skaters(game_ids)
        self.stdout.write(self.style.SUCCESS(f"  Updated {skater_count} skater rows."))

        self.stdout.write("Scoring goalies...")
        goalie_count = score_goalies(game_ids)
        self.stdout.write(self.style.SUCCESS(f"  Updated {goalie_count} goalie rows."))

        date_str = options["date"]
        self.stdout.write("Invalidating and warming leaderboard cache...")
        invalidate_leaderboard(date_str)
        warm_leaderboard(date_str)
        self.stdout.write(self.style.SUCCESS("  Cache ready."))
