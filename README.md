# HN Explorer

> Browse every *Who's Hiring?* thread from Hacker News — filtered, searchable, and self-hosted.

[![CI](https://github.com/vnturing/hnhired/actions/workflows/ci.yml/badge.svg)](https://github.com/vnturing/hnhired/actions/workflows/ci.yml)
[![Docker](https://github.com/vnturing/hnhired/actions/workflows/docker.yml/badge.svg)](https://github.com/vnturing/hnhired/actions/workflows/docker.yml)
[![Image](https://ghcr-badge.egpl.dev/vnturing/hnhired/latest_tag?trim=major&label=ghcr.io)](https://github.com/vnturing/hnhired/pkgs/container/hnhired)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

HN Explorer ingests HN *Who's Hiring?* threads into a local SQLite database and
serves them through a fast, filter-rich UI — no account, no tracking, no noise.

**Features**

- 🔍 **Boolean search** — `Python && (Go || Rust) && ~C++`
- 🗓️ **Month filter** — browse any historical thread, defaults to the latest
- 🌍 **Remote filter** — global remote · EU-only · timezone-limited · on-site
- 📌 **Persistent filters** — preferences survive reloads (localStorage + URL params)
- 🐳 **Single-container** — one `docker run` and it's live, DB included
- ♻️ **Auto-ingest** — re-ingests daily at 09:00; bootstraps from empty on first boot
- 🏗️ **Multi-arch** — `linux/amd64` and `linux/arm64` (Raspberry Pi ready)

---

## Quickstart

### Docker (recommended)

```sh
docker run -d --name hn-explorer \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  -p 8080:8000 \
  ghcr.io/vnturing/hnhired:latest
```

Open **http://localhost:8080** — the app bootstraps itself on first run.

### Docker Compose

```yaml
# docker-compose.yml
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

```sh
docker compose up -d
```

---

## Local development

**Prerequisites:** [uv](https://docs.astral.sh/uv/)

```sh
git clone https://github.com/vnturing/hnhired.git
cd hnhired

uv sync --all-extras --dev
make dev          # → http://localhost:8000
```

### Common tasks

| Command | Description |
|---|---|
| `make dev` | FastAPI dev server with auto-reload |
| `make test` | Run pytest suite |
| `make lint` | Ruff static analysis |
| `make fmt` | Black formatter |
| `make ingest` | Manual one-off ingest |

---

## Releasing

Versions follow [semver](https://semver.org/). Bumping the version commits,
tags, and pushes — the tag triggers GitHub Actions to build and publish a
multi-arch Docker image to GHCR.

```sh
make release-patch   # 0.1.0 → 0.1.1
make release-minor   # 0.1.0 → 0.2.0
make release-major   # 0.1.0 → 1.0.0
```

> [!NOTE]
> On first publish you may need to link the GHCR package to the repository
> and set its visibility to **Public** in the GitHub Package settings.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  FastAPI (app/)                                      │
│  ┌─────────────┐  ┌───────────────┐  ┌───────────┐  │
│  │  ingest.py  │→ │  parser.py    │→ │   db.py   │  │
│  │  HN API     │  │  classify     │  │  SQLite   │  │
│  │  scheduler  │  │  remote type  │  │  jobs.db  │  │
│  └─────────────┘  └───────────────┘  └───────────┘  │
│                                            ↓         │
│  ┌───────────────────────────────────────────────┐   │
│  │  static/  (Alpine.js + vanilla CSS)           │   │
│  │  Boolean search · month/remote/role filters   │   │
│  └───────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| Backend | FastAPI + uvicorn |
| Database | SQLite (via standard library) |
| Frontend | Alpine.js · Vanilla CSS |
| Packaging | uv · Docker (multi-arch) |
| CI/CD | GitHub Actions → GHCR |

---

## Contributing

1. Fork & clone
2. `uv sync --all-extras --dev`
3. Make your changes — add tests for new behaviour
4. `make lint && make test`
5. Open a PR

---

## License

[MIT](LICENSE)
