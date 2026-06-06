import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed the Celery beat periodic task schedule in the database (idempotent)."

    def handle(self, *args, **options):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="2",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        _, created = PeriodicTask.objects.get_or_create(
            name="nightly-pipeline",
            defaults={
                "task": "apps.core.tasks.nightly_pipeline",
                "crontab": schedule,
                "args": json.dumps([]),
                "enabled": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created nightly-pipeline task (runs at 2:00 AM UTC)."))
        else:
            self.stdout.write("nightly-pipeline task already exists — no changes made.")
