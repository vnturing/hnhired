# HN Explorer

A single-container app that ingests HN *Who's Hiring* threads and lets you
browse them with filters — built with FastAPI, Alpine.js, SQLite, and uv.

## Run locally

```sh
uv sync --all-extras --dev
uv run fastapi dev app/main.py
# → http://localhost:8000
```

On first boot the app auto-ingests the latest thread (empty DB).  It then
re-ingests every day at 09:00.

## Run tests (red/green TDD)

```sh
uv run pytest -v
# or:
make test
```

## Makefile helpers

```sh
make dev       # fastapi dev server
make test      # pytest
make lint      # ruff check
make fmt       # black format
make ingest    # manual one-off ingest
```

## Releasing a new version

Versions follow semver.  Pushing a tag triggers GitHub Actions to build and
push `ghcr.io/[owner]/hnhired:<version>` to GitHub Container Registry.

```sh
make release-patch   # 0.1.0 → 0.1.1
make release-minor   # 0.1.0 → 0.2.0
make release-major   # 0.1.0 → 1.0.0
```

To make the package public on GHCR, you may need to link it to the repository
and change its visibility settings the first time.

## Docker 

You can run the app locally by building the image, or you can use the published
image from GitHub Container Registry.

### Using `docker run`

```sh
docker pull ghcr.io/vnturing/hnhired:latest

docker run -d --name hn-explorer \\
  -v $(pwd)/data:/app/data \\
  --restart unless-stopped \\
  -p 8080:8000 \\
  ghcr.io/vnturing/hnhired:latest
```

### Using `docker compose`

Create a `docker-compose.yml` file:

```yaml
services:
  hn-explorer:
    image: ghcr.io/vnturing/hnhired:latest
    container_name: hn-explorer
    restart: unless-stopped
    ports:
      - "8080:8000"
    volumes:
      - ./data:/app/data
```

Then run:

```sh
docker compose up -d
```

The container automatically ingests the latest thread on first startup to 
populate the database. Every day thereafter (at 09:00 system time), it will 
seamlessly wake up in the background and ingest the current latest thread — no 
cron jobs or manual intervention needed.
