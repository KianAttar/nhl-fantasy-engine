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
    print('Dev admin created — login: admin / admin')
"

exec "$@"
