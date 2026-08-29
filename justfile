# Common developer tasks. Run `just` to list recipes, `just install` to set up
# a machine, and `just doctor` to diagnose one.
#
# PORTABILITY: these recipes run on macOS, Linux, and Windows. Every recipe is
# a single command -- anything needing real logic lives in `scripts/*.py` and
# is invoked through `uv`, so no recipe depends on bash, POSIX utilities, or
# PowerShell. Keep it that way: if a recipe needs a loop, a conditional, or a
# cleanup handler, write it in Python instead.
#
# The only hard prerequisite is `uv`; `just` itself installs from PyPI
# (`uv tool install rust-just`) on all three platforms.

# Windows has no bash by default; `just` falls back to this for shell recipes.
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Container engine. Override with `just container=docker <recipe>`.
container := "podman"

# List available recipes.
default:
    @just --list

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Install every required tool (and optional ones if possible), then report.
install:
    uv run python scripts/toolchain.py install --engine {{ container }}

# Report the status of the toolchain without changing anything.
doctor:
    uv run python scripts/toolchain.py doctor --engine {{ container }}

# Install/refresh the workspace dev environment (installs every server too).
sync:
    uv sync --all-packages

# Install the pre-commit git hook (one-time setup).
install-hooks:
    uvx pre-commit install

# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

# Lint Python with ruff.
lint:
    uv run ruff check .

# Auto-fix Python lint issues where possible.
lint-fix:
    uv run ruff check --fix .

# Check Python + TOML formatting without writing changes.
fmt-check:
    uv run ruff format --check .
    uv run taplo fmt --check

# Format Python and TOML.
fmt:
    uv run ruff format .
    uv run taplo fmt

# Type-check repo-level code with ty (excludes PEP 723 scripts; see AGENTS.md).
typecheck:
    uv run ty check .

# Spell-check source and docs.
spell:
    uv run typos

# Run the full test suite (repo-level + every server's tests).
test:
    uv run pytest

# Run only the fast tests (skip subprocess/network round trips).
test-fast:
    uv run pytest -m "not slow"

# Run tests with a coverage report; see cov_annotate/ for line-by-line detail.
coverage:
    uv run pytest --cov --cov-report=term-missing --cov-report=annotate:cov_annotate

# Update inline-snapshot values after an intentional change (review the diff!).
snapshot-fix:
    uv run pytest --inline-snapshot=fix

# Scan for vulnerabilities, secrets, and misconfigurations (skips if no trivy).
security:
    uv run python scripts/security_scan.py

# Run every check used before committing.
check: lint fmt-check typecheck spell test security
    @echo "All checks passed."

# Run every pre-commit hook against all files.
pre-commit-all:
    uvx pre-commit run --all-files

# ---------------------------------------------------------------------------
# Plugins and servers
# ---------------------------------------------------------------------------

# Scaffold a new plugin from the example-plugin pattern.
new-plugin name:
    uv run python scripts/new_plugin.py {{ name }}

# Scaffold a new FastMCP server inside an existing plugin.
new-server plugin name:
    uv run python scripts/new_server.py {{ plugin }} {{ name }}

# Inspect a server's MCP surface (tools/resources/prompts) as a JSON report.
inspect-server plugin server:
    uv run fastmcp inspect {{ plugin }}/servers/{{ server }}/fastmcp.json

# Run a server directly (no container) on http://127.0.0.1:<port>/mcp
run-server server port="8000":
    uv run python scripts/run_server.py {{ server }} --port {{ port }}

# Re-download the canonical Agent Plugins JSON Schemas.
update-schemas version="1.0.0":
    uv run python scripts/update_schemas.py {{ version }}

# ---------------------------------------------------------------------------
# Containers (podman by default; `just container=docker ...` for docker)
# ---------------------------------------------------------------------------

# Build a server's image. `--format docker` preserves HEALTHCHECK.
image-build plugin server tag="latest":
    {{ container }} build --format docker -f {{ plugin }}/servers/{{ server }}/Dockerfile -t {{ server }}:{{ tag }} .

# Run a server's image locally on http://127.0.0.1:<port>/mcp
image-run server port="8000" tag="latest":
    {{ container }} run --rm -p {{ port }}:8000 {{ server }}:{{ tag }}

# Build the image, run it, and verify the MCP endpoint answers over HTTP.
image-smoke plugin server:
    uv run python scripts/image_smoke.py {{ plugin }} {{ server }} --engine {{ container }}
