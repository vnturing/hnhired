# syntax=docker/dockerfile:1
# ──────────────────────────────────────────────────────────────────────────────
# Single-stage build.  uv resolves the lockfile; no Node, no build pipeline.
# The same image runs on your laptop (amd64) and your Pi (arm64) because
# GitHub Actions builds both via QEMU — see .github/workflows/build.yml.
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim-bullseye

# Install uv — the only extra tool we need.
RUN pip install uv --no-cache-dir

WORKDIR /app

# Dependency layer — copy lockfiles first so Docker cache is reused when only
# app code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Application code and static assets.
COPY app/ app/

# The data/ directory is intentionally NOT baked in.
# Mount it at runtime: -v $(pwd)/data:/app/data
# This keeps the DB outside the image and survives container restarts.
RUN mkdir -p data

EXPOSE 8000

# uv run ensures the venv is active and PATH is correct.
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
