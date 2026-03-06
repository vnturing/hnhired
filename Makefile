# ── Release targets ───────────────────────────────────────────────────────────
# Usage:
#   make release-patch   0.1.0 → 0.1.1
#   make release-minor   0.1.0 → 0.2.0
#   make release-major   0.1.0 → 1.0.0
#
# Each target bumps the version in pyproject.toml, commits, tags, and pushes.
# The git tag push triggers the GitHub Actions docker.yml workflow.

.PHONY: release-patch release-minor release-major _release

# Read current version from pyproject.toml (e.g. version = "0.1.0")
CURRENT_VERSION := $(shell grep -m1 '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

_MAJOR := $(word 1,$(subst ., ,$(CURRENT_VERSION)))
_MINOR := $(word 2,$(subst ., ,$(CURRENT_VERSION)))
_PATCH := $(word 3,$(subst ., ,$(CURRENT_VERSION)))

release-patch:
	$(MAKE) _release NEW_VERSION="$(_MAJOR).$(_MINOR).$(shell echo $$(( $(_PATCH) + 1 )))"

release-minor:
	$(MAKE) _release NEW_VERSION="$(_MAJOR).$(shell echo $$(( $(_MINOR) + 1 ))).0"

release-major:
	$(MAKE) _release NEW_VERSION="$(shell echo $$(( $(_MAJOR) + 1 ))).0.0"

_release:
ifndef NEW_VERSION
	$(error NEW_VERSION is not set — call a release-* target, not _release directly)
endif
	@echo "Bumping $(CURRENT_VERSION) → $(NEW_VERSION)"
	@sed -i 's/^version = "$(CURRENT_VERSION)"/version = "$(NEW_VERSION)"/' pyproject.toml
	@git add pyproject.toml
	@git commit -m "chore: release v$(NEW_VERSION)"
	@git tag -a "v$(NEW_VERSION)" -m "Release v$(NEW_VERSION)"
	@git push origin HEAD
	@git push origin "v$(NEW_VERSION)"
	@echo "✓ Tagged and pushed v$(NEW_VERSION) — CI will build and push the Docker image."


# ── Dev helpers ───────────────────────────────────────────────────────────────

.PHONY: dev test lint fmt ingest

dev:
	uv run fastapi dev app/main.py

test:
	uv run pytest -v

lint:
	uv run ruff check app/ tests/

fmt:
	uv run black app/ tests/

ingest:
	uv run python -m app.ingest
