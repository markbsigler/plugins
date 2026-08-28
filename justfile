# Common developer tasks for this repo. Run `just` (or `just --list`) to see
# all recipes, and `just install` to set up a new machine.
#
# Container images are built and run with podman (rootless, daemonless).
# The Dockerfile is OCI-standard, so docker works too if you prefer it:
#   just container=docker docker-build ...

set shell := ["bash", "-euo", "pipefail", "-c"]

# Container engine. Override with `just container=docker <recipe>`.
container := "podman"

# List available recipes.
default:
    @just --list

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Install every required tool, then sync the workspace. Safe to re-run.
install: install-tools sync
    @echo ""
    @just doctor

# Install the required external tooling (uv, just, podman, trivy, pre-commit).
[private]
install-tools:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v brew >/dev/null 2>&1; then
        echo "error: Homebrew not found."
        echo "Install the following manually, then re-run 'just sync':"
        echo "  uv      https://docs.astral.sh/uv/getting-started/installation/"
        echo "  just    https://just.systems/man/en/packages.html"
        echo "  podman  https://podman.io/docs/installation"
        echo "  trivy   https://trivy.dev/latest/getting-started/installation/"
        exit 1
    fi
    for tool in uv just podman trivy; do
        if command -v "$tool" >/dev/null 2>&1; then
            echo "ok       $tool already installed"
        else
            echo "install  $tool"
            brew install "$tool"
        fi
    done
    # Ruff, ty, taplo, typos, pytest and friends are Python tools and come
    # from the uv workspace (see `just sync`), not from Homebrew.

# Report the status of every required tool and the podman machine.
doctor:
    #!/usr/bin/env bash
    set -uo pipefail
    status=0
    echo "Required tools"
    for tool in uv just podman trivy; do
        if command -v "$tool" >/dev/null 2>&1; then
            case "$tool" in
                # `trivy --version` loads trivy.yaml and prints INFO noise.
                trivy) version=$(trivy -q version 2>/dev/null | head -1) ;;
                *)     version=$("$tool" --version 2>&1 | head -1) ;;
            esac
            printf '  %-8s %s\n' "$tool" "$version"
        else
            printf '  %-8s MISSING -- run: just install\n' "$tool"
            status=1
        fi
    done
    echo ""
    echo "Workspace tools (from uv)"
    for tool in ruff ty taplo typos pytest; do
        if uv run --quiet "$tool" --version >/dev/null 2>&1; then
            printf '  %-8s ok\n' "$tool"
        else
            printf '  %-8s MISSING -- run: just sync\n' "$tool"
            status=1
        fi
    done
    echo ""
    echo "Container engine ({{ container }})"
    engine_ready=1
    if command -v {{ container }} >/dev/null 2>&1; then
        if {{ container }} info >/dev/null 2>&1; then
            echo "  ready"
            engine_ready=0
        else
            echo "  installed but not running"
            if [ "{{ container }}" = "podman" ]; then
                echo "  start it with: podman machine init   # first time only"
                echo "                 podman machine start"
            fi
        fi
    else
        echo "  MISSING -- run: just install"
        status=1
    fi
    echo ""
    if [ "$status" -ne 0 ]; then
        echo "Some required tooling is missing."
    elif [ "$engine_ready" -ne 0 ]; then
        echo "All tools installed. Start the container engine to build images."
    else
        echo "All required tooling present and ready."
    fi
    exit "$status"

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

# Re-download the canonical Agent Plugins JSON Schemas.
update-schemas version="1.0.0":
    mkdir -p schemas/{{ version }}
    curl -fsSL https://agent-plugins.org/schemas/{{ version }}/plugin.schema.json \
        -o schemas/{{ version }}/plugin.schema.json
    curl -fsSL https://agent-plugins.org/schemas/{{ version }}/mcp.schema.json \
        -o schemas/{{ version }}/mcp.schema.json
    @echo "Updated schemas/{{ version }}/ -- review the diff before committing."

# ---------------------------------------------------------------------------
# Containers (podman by default)
# ---------------------------------------------------------------------------

# Build a server's image. Runs from the repo root so uv.lock is in context.
# `--format docker` preserves HEALTHCHECK, which the default OCI format drops.
image-build plugin server tag="latest":
    {{ container }} build --format docker \
        -f {{ plugin }}/servers/{{ server }}/Dockerfile \
        -t {{ server }}:{{ tag }} .

# Run a server's image locally on http://127.0.0.1:<port>/mcp
image-run server port="8000" tag="latest":
    {{ container }} run --rm -p {{ port }}:8000 {{ server }}:{{ tag }}

# Build the image and verify the served MCP endpoint answers over HTTP.
image-smoke plugin server port="8765": (image-build plugin server)
    #!/usr/bin/env bash
    set -euo pipefail
    cid=$({{ container }} run -d -p {{ port }}:8000 {{ server }}:latest)
    trap '{{ container }} rm -f "$cid" >/dev/null 2>&1 || true' EXIT
    for _ in $(seq 1 30); do
        if uv run python -c "import socket;socket.create_connection(('127.0.0.1',{{ port }}),timeout=1).close()" 2>/dev/null; then
            break
        fi
        sleep 1
    done
    uv run python -c "
    import asyncio
    from fastmcp import Client
    async def main():
        async with Client('http://127.0.0.1:{{ port }}/mcp') as c:
            print('tools:', sorted(t.name for t in await c.list_tools()))
    asyncio.run(main())
    "
    echo "Container smoke test passed."
