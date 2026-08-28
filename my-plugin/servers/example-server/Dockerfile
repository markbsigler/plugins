# Multi-stage build for the example FastMCP server.
#
# Build from the *repository root* so the uv workspace lockfile is available:
#
#   docker build -f my-plugin/servers/example-server/Dockerfile -t example-server .
#
# The root `uv.lock` pins every workspace member together, so image builds are
# reproducible and match local development exactly.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first, in their own layer, so edits to server source
# don't invalidate the (slow) dependency layer.
COPY pyproject.toml uv.lock ./
COPY my-plugin/servers/example-server/pyproject.toml my-plugin/servers/example-server/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev \
        --package example-server

COPY my-plugin/servers/example-server/ my-plugin/servers/example-server/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev \
        --package example-server


FROM python:3.12-slim-bookworm AS runtime

# Run as an unprivileged user.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000 \
    FASTMCP_PATH=/mcp

COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER app
WORKDIR /app
EXPOSE 8000

# Streamable HTTP requires an MCP-aware client for a true protocol check; a
# TCP-level connect is enough to detect a dead or wedged process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket,os,sys; s=socket.create_connection(('127.0.0.1', int(os.environ['FASTMCP_PORT'])), timeout=3); s.close()" || exit 1

CMD ["python", "-m", "example_server"]
