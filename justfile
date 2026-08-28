# Common developer tasks for this repo. Run `just` (or `just --list`) to see
# all recipes. Requires `just` (https://just.systems/) and `uv`; install
# `just` however you prefer (e.g. `brew install just`) — it isn't a Python
# package, so `uv`/`uvx` can't install it.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List available recipes.
default:
    @just --list

# Install/refresh the repo dev tool virtualenv (ruff, ty, pytest, ...).
sync:
    uv sync

# Lint with ruff.
lint:
    uv run ruff check .

# Auto-fix lint issues where possible.
lint-fix:
    uv run ruff check --fix .

# Check formatting without writing changes.
fmt-check:
    uv run ruff format --check .

# Format all files with ruff.
fmt:
    uv run ruff format .

# Type-check repo-level code with ty (excludes PEP 723 scripts; see AGENTS.md).
typecheck:
    uv run ty check .

# Run the full test suite.
test:
    uv run pytest

# Run only the fast tests (skip subprocess-spawned server integration tests).
test-fast:
    uv run pytest -m "not slow"

# Update inline-snapshot values after an intentional change (review the diff before committing).
snapshot-fix:
    uv run pytest --inline-snapshot=fix

# Scan for vulnerabilities, secrets, and misconfigurations with trivy.
security:
    trivy fs --config trivy.yaml .

# Run every check used before committing (see AGENTS.md §3.8).
check: lint fmt-check typecheck test security
    @echo "All checks passed."

# Run every check pre-commit will also run, against all files.
pre-commit-all:
    uvx pre-commit run --all-files
