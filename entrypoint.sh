#!/bin/sh
set -e

# Fall back to .env.example if no .env is present (dev convenience)
if [ ! -f .env ]; then
    echo "No .env found — using .env.example defaults"
    cp .env.example .env
fi

# Run migrations
python manage.py migrate --noinput

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
    print('     username: admin')
    print('     password: admin')
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
    print('')
"

exec "$@"
