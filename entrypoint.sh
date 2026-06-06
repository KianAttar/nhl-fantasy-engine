#!/bin/sh
set -e

# Fall back to .env.example if no .env is present (dev convenience)
if [ ! -f .env ]; then
    echo "No .env found — using .env.example defaults"
    cp .env.example .env
fi

# Run migrations
python manage.py migrate --noinput

# Create the DB cache table (no-op if it already exists)
python manage.py createcachetable --no-color 2>/dev/null || true

# Create default admin only when DEBUG=True (never in production)
python manage.py shell -c "
from django.conf import settings
from django.contrib.auth.models import User
if settings.DEBUG and not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
"

# Print dev banner
python manage.py shell -c "
from django.conf import settings
if settings.DEBUG:
    print('')
    print('  ================================================')
    print('   NHL Fantasy Engine — dev server ready')
    print('  ================================================')
    print('')
    print('   Admin dashboard')
    print('     http://localhost:8000/admin/')
    print('     username: admin  |  password: admin')
    print('')
    print('   API endpoints')
    print('     Leaderboard (all-time):')
    print('       http://localhost:8000/api/leaderboard/')
    print('')
    print('     Leaderboard (single day):')
    print('       http://localhost:8000/api/leaderboard/?date=YYYY-MM-DD')
    print('')
    print('     Leaderboard (custom page size, max 200):')
    print('       http://localhost:8000/api/leaderboard/?page_size=100')
    print('')
    print('     Player stats:')
    print('       http://localhost:8000/api/players/{id}/stats/')
    print('')
    print('  ================================================')
    print('   Database is empty. Open a new terminal and run:')
    print('  ================================================')
    print('')
    print('   Seed rosters (run once before ingesting):')
    print('     docker exec nhl-fantasy python manage.py ingest_games --seed-rosters')
    print('')
    print('   Ingest today only:')
    print('     docker exec nhl-fantasy sh -c \"python manage.py ingest_games --days 1 && python manage.py score_games\"')
    print('')
    print('   Ingest past week:')
    print('     docker exec nhl-fantasy sh -c \"python manage.py ingest_games --days 7 && python manage.py score_games\"')
    print('')
    print('   Ingest past month:')
    print('     docker exec nhl-fantasy sh -c \"python manage.py ingest_games --days 30 && python manage.py score_games\"')
    print('')
    print('   Ingest past 3 months:')
    print('     docker exec nhl-fantasy sh -c \"python manage.py ingest_games --days 90 && python manage.py score_games\"')
    print('')
    print('   NOTE: Start the container with --name nhl-fantasy for the above commands to work:')
    print('     docker run --name nhl-fantasy -p 8000:8000 kiancode/nhl-fantasy-engine')
    print('')
    print('  ================================================')
    print('')
"

exec "$@"
