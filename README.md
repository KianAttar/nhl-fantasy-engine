# NHL Fantasy Points Engine

A Django app that ingests real NHL game stats, calculates fantasy points using NumPy, and exposes a leaderboard API — with Celery handling scheduled ingestion.

## Stack

- **Python / Django** — data models, ORM, management commands
- **NumPy + memmap** — vectorized scoring engine, stat matrix cached to disk
- **Django REST Framework** — leaderboard and player stats API
- **Celery + Redis** — async ingestion pipeline, nightly beat schedule
- **PostgreSQL** — primary data store
- **Docker Compose** — one command to run the full stack

## Data Source

Live stats from the free public NHL API — no API key required.

## Architecture

```
NHL API (free, public)
    │
    │  HTTP (requests + retry)
    ▼
[Celery Worker]  ←── celery beat (nightly cron)
    │
    │  parse + normalize
    ▼
[PostgreSQL]  ←── Django ORM (update_or_create / bulk_create)
    │
    │  load stat matrix
    ▼
[NumPy Engine]  ←── numpy.memmap cache on disk
    │
    │  bulk_update points
    ▼
[PostgreSQL leaderboard]
    │
    │  DRF serializers + CursorPagination
    ▼
GET /api/leaderboard/
```

## Stages

| Stage | What gets built |
|---|---|
| 1 | Django project, schema, migrations |
| 2 | NHL API ingestion, management command |
| 3 | NumPy scoring engine, memmap cache |
| 4 | DRF leaderboard and player stats API |
| 5 | Celery tasks, beat schedule, Docker Compose |
| 6 | Tests, CI, documentation |

## Setup

```bash
cp .env.example .env
docker-compose up
```

API available at `http://localhost:8000/api/`.
