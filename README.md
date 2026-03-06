# HN Explorer

A single-container app that ingests HN *Who's Hiring* threads and lets you
browse them with filters — built with FastAPI, Alpine.js, SQLite, and uv.

## Run locally

```sh
uv sync
uv run fastapi dev app/main.py
# → http://localhost:8000
```

## Run tests (red/green TDD)

```sh
uv run pytest -v
```

Tests run in dependency order:
- `test_step1_health.py`   — health route
- `test_step2_static.py`   — static file serving
- `test_step3_jobs_api.py` — /api/jobs shape + filtering
- `test_step4_parser.py`   — pure extraction functions
- `test_step5_db.py`       — SQLite persistence layer
- `test_step6_ingest.py`   — HN API ingestion (mocked)
- `test_step7_integration.py` — full stack with DB dependency

## Ingest a thread

To fetch and ingest the latest "Who's Hiring?" thread automatically:

```sh
uv run python -m app.ingest
```

You can also ingest a specific thread by passing its HN ID (e.g. `https://news.ycombinator.com/item?id=39894820`):

```sh
uv run python -m app.ingest 39894820
```

## Docker

```sh
# Build locally
docker build -t hn-explorer .

# Run (mounts ./data so the DB survives restarts)
docker run -d --name hn-explorer \
  -v $(pwd)/data:/app/data \
  -p 8080:8000 \
  hn-explorer
```

## Deploy on Raspberry Pi

On the Pi, after GitHub Actions pushes the multi-arch image:

```sh
docker pull yourname/hn-explorer:latest
docker run -d --name hn-explorer \
  -v $(pwd)/data:/app/data \
  -p 8080:8000 \
  yourname/hn-explorer:latest
```

Ingest monthly (add to crontab):

```sh
0 9 1 * * docker exec hn-explorer uv run python -m app.ingest
```
