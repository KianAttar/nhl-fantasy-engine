from django.db import migrations


SKATER_RULES = [
    ("goals",            4.0),
    ("assists",          2.0),
    ("shots",            0.5),
    ("hits",             0.5),
    ("plus_minus",       1.0),
    ("pim",              0.25),
    ("power_play_goals", 1.0),   # bonus on top of the regular goal points
    ("blocked_shots",    0.5),
    ("takeaways",        0.5),
    ("giveaways",       -0.5),
]

GOALIE_RULES = [
    ("saves",         0.2),
    ("goals_against", -1.0),
    ("shots_against",  0.0),   # stored but not scored by default
    ("win",            5.0),
    ("ot_loss",        1.0),
]


def seed_rules(apps, schema_editor):
    SkaterScoringRule = apps.get_model("core", "SkaterScoringRule")
    GoalieScoringRule = apps.get_model("core", "GoalieScoringRule")

    for stat_name, points in SKATER_RULES:
        SkaterScoringRule.objects.get_or_create(
            stat_name=stat_name,
            defaults={"points_per_unit": points},
        )

    for stat_name, points in GOALIE_RULES:
        GoalieScoringRule.objects.get_or_create(
            stat_name=stat_name,
            defaults={"points_per_unit": points},
        )


def unseed_rules(apps, schema_editor):
    apps.get_model("core", "SkaterScoringRule").objects.all().delete()
    apps.get_model("core", "GoalieScoringRule").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_goaliescoringrule_skaterscoringrule_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_rules, reverse_code=unseed_rules),
    ]
