from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from apps.core.services.ingestion import ingest_date, seed_rosters
from apps.core.services.nhl_client import NHLClient


class Command(BaseCommand):
    help = "Ingest NHL game stats for a given date from the public NHL API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Date to ingest in YYYY-MM-DD format. Defaults to today.",
        )
        parser.add_argument(
            "--seed-rosters",
            action="store_true",
            default=False,
            help="Seed all 32 team rosters before ingesting games (run once on first setup).",
        )

    def handle(self, *args, **options):
        client = NHLClient()

        if options["seed_rosters"]:
            self.stdout.write("Seeding rosters for all 32 teams...")
            teams_count, players_count = seed_rosters(client)
            self.stdout.write(
                self.style.SUCCESS(f"  Seeded {players_count} players across {teams_count} teams.")
            )

        date_str = options["date"]
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise CommandError(f"Invalid date format: '{date_str}'. Use YYYY-MM-DD.")
        else:
            target_date = date.today()

        self.stdout.write(f"Ingesting games for {target_date}...")
        summary = ingest_date(client, target_date)

        if summary["games"] == 0:
            self.stdout.write(self.style.WARNING(f"  No completed games found for {target_date}."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Done. {summary['games']} games | "
                    f"{summary['skater_stats']} skater stats | "
                    f"{summary['goalie_stats']} goalie stats"
                )
            )
