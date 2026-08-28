# Common developer tasks for this repo. Run `just` (or `just --list`) to see
# all recipes. Requires `just` (https://just.systems/), `uv`, and `trivy`;
# install `just` and `trivy` however you prefer (e.g. `brew install just
# trivy`) -- they are Rust/Go binaries, not Python packages.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List available recipes.
default:
    @just --list

# Install/refresh the workspace dev environment. `--all-packages` installs
# every MCP server in the workspace, so new servers work with no extra wiring.
sync:
    uv sync --all-packages

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

# Update inline-snapshot values after an intentional change (review the diff!).
snapshot-fix:
    uv run pytest --inline-snapshot=fix

# Scan for vulnerabilities, secrets, and misconfigurations with trivy.
security:
    trivy fs --config trivy.yaml .

# Run every check used before committing.
check: lint fmt-check typecheck spell test security
    @echo "All checks passed."

# Run every pre-commit hook against all files.
pre-commit-all:
    uvx pre-commit run --all-files

# Install the pre-commit git hook (one-time setup).
install-hooks:
    uvx pre-commit install

# Re-download the canonical Agent Plugins JSON Schemas.
update-schemas version="1.0.0":
    mkdir -p schemas/{{ version }}
    curl -fsSL https://agent-plugins.org/schemas/{{ version }}/plugin.schema.json \
        -o schemas/{{ version }}/plugin.schema.json
    curl -fsSL https://agent-plugins.org/schemas/{{ version }}/mcp.schema.json \
        -o schemas/{{ version }}/mcp.schema.json
    @echo "Updated schemas/{{ version }}/ -- review the diff before committing."

# Scaffold a new plugin from the my-plugin example.
new-plugin name:
    uv run python scripts/new_plugin.py {{ name }}

# Scaffold a new FastMCP server inside an existing plugin.
new-server plugin name:
    uv run python scripts/new_server.py {{ plugin }} {{ name }}

# Inspect a server's MCP surface (tools/resources/prompts) as a JSON report.
inspect-server plugin server:
    uv run fastmcp inspect {{ plugin }}/servers/{{ server }}/fastmcp.json

# Build a server's container image (run from the repo root).
docker-build plugin server tag="latest":
    docker build -f {{ plugin }}/servers/{{ server }}/Dockerfile -t {{ server }}:{{ tag }} .

# Run a server's container image locally.
docker-run server port="8000" tag="latest":
    docker run --rm -p {{ port }}:8000 {{ server }}:{{ tag }}
