# NHL Fantasy Points Engine

A Django app that ingests real NHL game stats, calculates fantasy points using NumPy, and exposes a leaderboard API — with Celery handling scheduled ingestion.

**Stack:** Python, Django, Django REST Framework, NumPy, Celery, Redis, PostgreSQL, Docker

---

## Architecture

```
NHL API (free, public)
    │
    │  HTTP (requests + retry)
    ▼
[Celery Worker]  <── celery beat (nightly cron, 2 AM UTC)
    │
    │  parse + normalize (update_or_create — idempotent)
    ▼
[PostgreSQL]  <── Django ORM
    │
    │  load stat arrays
    ▼
[NumPy Scoring Engine]  (vectorized matrix multiply — no Python loops)
    │
    │  bulk_update fantasy_points
    ▼
[PostgreSQL leaderboard]
    │
    │  DRF serializers + cache (Redis in prod, locmem in dev)
    ▼
GET /api/leaderboard/
GET /api/players/{id}/stats/
```

---

## Running in development (single Docker command)

No configuration needed. SQLite and in-memory cache are used by default — no Redis or Postgres required.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/)

```bash
docker run --name nhl-fantasy -p 8000:8000 kiancode/nhl-fantasy-engine
```

That's it. On first run this will:
- Apply all migrations automatically
- Create a default admin user (`admin` / `admin`)
- Print the startup banner with all URLs and ingestion commands

API at `http://localhost:8000/api/` — Admin at `http://localhost:8000/admin/`

> If you want to use a custom `.env`, mount it:
> ```bash
> docker run --name nhl-fantasy -p 8000:8000 -v $(pwd)/.env:/app/.env kiancode/nhl-fantasy-engine
> ```

### Ingest data (in a second terminal)

The database starts empty. Use `docker exec` against the running container to populate it.

```bash
# Seed all 32 team rosters (run once before ingesting)
docker exec nhl-fantasy python manage.py ingest_games --seed-rosters

# Ingest today only + score
docker exec nhl-fantasy sh -c "python manage.py ingest_games --days 1 && python manage.py score_games"

# Ingest past week + score
docker exec nhl-fantasy sh -c "python manage.py ingest_games --days 7 && python manage.py score_games"

# Ingest past month + score
docker exec nhl-fantasy sh -c "python manage.py ingest_games --days 30 && python manage.py score_games"

# Ingest past 3 months + score
docker exec nhl-fantasy sh -c "python manage.py ingest_games --days 90 && python manage.py score_games"
```

### Running tests

```bash
docker run kiancode/nhl-fantasy-engine python manage.py test apps.core --verbosity=2
```

---

## Running locally without Docker

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/)

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd nhl-fantasy-engine
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

### 3. Run migrations

```bash
uv run python manage.py migrate
```

### 4. Create an admin user

```bash
uv run python manage.py createsuperuser
```

Admin is at `http://localhost:8000/admin/`.

### 5. Ingest NHL data


Seed all 32 team rosters (run once):

```bash
uv run python manage.py ingest_games --seed-rosters
```

Ingest games for a specific date:

```bash
uv run python manage.py ingest_games --date 2024-01-15
```

### 6. Score the ingested stats

```bash
uv run python manage.py score_games --date 2024-01-15
```

### 7. Start the dev server

```bash
uv run python manage.py runserver
```

API is now at `http://localhost:8000/api/`.

### Running Celery (optional for local dev)

If you want the full async pipeline locally, you need Redis running first (`brew install redis && brew services start redis` on macOS), then:

```bash
# Worker (processes tasks)
uv run celery -A config worker --loglevel=info

# Beat scheduler (triggers the nightly cron)
uv run celery -A config beat --loglevel=info
```

### Running tests

```bash
uv run python manage.py test apps.core --verbosity=2
```

---

## Running with Docker (production-like)

Use this to run the full stack: Django + PostgreSQL + Redis + Celery worker + beat scheduler.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### 1. Clone the repo

```bash
git clone <repo-url>
cd nhl-fantasy-engine
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set:

```
SECRET_KEY=a-long-random-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
SENTRY_DSN=                          # optional — paste your Sentry DSN here
```

> `DATABASE_URL`, `REDIS_URL`, and `CACHE_URL` are set automatically by `docker-compose.yml`
> and will override anything you put in `.env` for those keys.

### 3. Build and start all services

```bash
docker-compose up --build
```

This starts:

- `postgres` — PostgreSQL 16
- `redis` — Redis 7
- `web` — Django + Gunicorn on port 8000 (runs migrations automatically on start)
- `worker` — Celery worker (2 concurrent processes)
- `beat` — Celery beat scheduler (nightly pipeline at 2 AM UTC)

### 4. Seed data (first run only)

In a second terminal, run the roster seed and an initial ingest:

```bash
docker-compose exec web python manage.py ingest_games --seed-rosters
docker-compose exec web python manage.py ingest_games --date 2024-01-15
docker-compose exec web python manage.py score_games --date 2024-01-15
```

After the first seed, the Celery beat job picks up new games automatically every night.

### 5. Access the API

```
http://localhost:8000/api/leaderboard/
http://localhost:8000/api/players/{id}/stats/
```

### Stopping

```bash
docker-compose down          # stop containers, keep DB volume
docker-compose down -v       # stop containers and delete DB volume
```

---

## API Reference

### `GET /api/leaderboard/`

Returns players ranked by total fantasy points, descending.

| Parameter   | Type         | Description                                     |
| ----------- | ------------ | ----------------------------------------------- |
| `date`      | `YYYY-MM-DD` | Filter to a single game day. Omit for all-time. |
| `page_size` | integer      | Results per page (default 50, max 200).         |

**Example response:**

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    { "player_id": 1, "total_points": 13.5, "team": "TOR", "position": "C" },
    { "player_id": 2, "total_points": 8.6, "team": "TOR", "position": "G" },
    { "player_id": 3, "total_points": 2.0, "team": "BOS", "position": "G" }
  ]
}
```

### `GET /api/players/{id}/stats/`

Returns a player's full profile with game-by-game stats.

**Example response:**

```json
{
  "id": 1,
  "first_name": "Auston",
  "last_name": "Matthews",
  "position": "C",
  "team": "TOR",
  "skater_stats": [
    {
      "game_date": "2024-01-15",
      "opponent": "BOS",
      "goals": 2,
      "assists": 1,
      "shots": 4,
      "fantasy_points": 13.5
    }
  ],
  "goalie_stats": []
}
```

---

## Default Scoring Weights

| Stat            | Points |
| --------------- | ------ |
| Goal            | 4.0    |
| Assist          | 2.0    |
| Shot on goal    | 0.5    |
| Hit             | 0.5    |
| +/-             | 1.0    |
| PIM             | 0.25   |
| Power play goal | 1.0    |
| Blocked shot    | 0.5    |
| Takeaway        | 0.5    |
| Giveaway        | -0.5   |
| Goalie save     | 0.2    |
| Goals against   | -1.0   |
| Win             | 5.0    |
| OT loss         | 1.0    |

Weights are stored in the `SkaterScoringRule` / `GoalieScoringRule` tables — adjustable without a code deploy.

---

## Performance

Load tested with [Locust](https://locust.io) against the full Docker stack (2 CPU / 2 GB RAM hard limit, 4 Gunicorn workers, PostgreSQL, Redis cache). Dataset: 529 scored players, ~4,500 stat rows across 2 months of NHL games.

### WSGI (Gunicorn sync workers) — production config

| Concurrent Users | RPS | p50 | p95 | p99 | Failures |
|---|---|---|---|---|---|
| 100 | 77 | 5ms | 12ms | 64ms | 0% |
| 1,000 | 643 | 210ms | 700ms | 1,400ms | 0% |
| 10,000 | 104 | 3,400ms | timeout | timeout | 9.8% |

**Breaking point: ~1,000–2,000 concurrent users.** At 1,000 the system was stressed but stable (0 failures, p95 under 1s). At 10,000 the Gunicorn worker queue saturated — requests piled up faster than workers could drain them, causing timeouts and a collapse in throughput (643 → 104 RPS).

**The cache is critical.** The leaderboard is a heavy aggregation query across thousands of stat rows. Redis cache-hit responses are served in ~5ms. Without the cache, every request would hit Postgres and the system would likely buckle below 100 users.

### ASGI (Gunicorn + uvicorn workers) — same hardware, same worker count

| Concurrent Users | RPS | p50 | p95 | Failures |
|---|---|---|---|---|
| 1,000 | 230 | 2,800ms | 5,500ms | ~0% |

**ASGI was 2.8× slower than WSGI for this codebase.** The reason: all views are synchronous. When a sync view runs through an ASGI server, Django wraps it in `sync_to_async` with `thread_sensitive=True` — meaning all sync views per worker are serialized through a single thread. This adds async/thread overhead on every request with no concurrency benefit.

ASGI only outperforms WSGI when views are truly async (`async def`) with async ORM calls (`await qs.afilter(...)`) and an async cache client. For a synchronous Django codebase, WSGI sync workers are the right choice.

### To scale further

| Approach | Expected gain |
|---|---|
| `--worker-class gevent` in Gunicorn | ~3–5× RPS on I/O-bound views, same CPU |
| Horizontal scaling (2× web replicas behind nginx) | ~2× linear RPS improvement |
| Async views + async ORM (Django 4.1+) | Unlocks true ASGI concurrency |
| Pre-warm all date-range cache keys after scoring | Eliminates cold-cache first-hit latency |

---

## Key Design Decisions

| Decision                          | Why                                                                                                |
| --------------------------------- | -------------------------------------------------------------------------------------------------- |
| `update_or_create` for ingestion  | Celery tasks retry on failure — ingestion must be idempotent                                       |
| NumPy matrix multiply for scoring | One vectorized `matrix @ weights` call scores all players at once — no Python loops                |
| Celery chord for scoring          | Skater and goalie scoring run in parallel; cache refresh fires only after both complete            |
| Cache leaderboard after scoring   | Leaderboard query is expensive; cache is invalidated and re-warmed at the end of each pipeline run |
| Scoring weights in DB, not code   | Scoring systems change — configurable without a code deploy                                        |
| `ScoringRule` seed migration      | Weights are part of the schema, version-controlled alongside the models                            |
