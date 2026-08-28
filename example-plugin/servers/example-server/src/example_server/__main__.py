"""Console entrypoint: ``python -m example_server``.

Transport and hosting concerns live here rather than in ``server.py`` so the
``mcp`` object stays import-clean for in-memory tests.

The server speaks MCP's Streamable HTTP transport; see
https://modelcontextprotocol.io/specification/ for the protocol and
https://gofastmcp.com/deployment/http for FastMCP's HTTP deployment guide.

Configuration is read from the environment so the same image runs in every
environment:

``FASTMCP_HOST``
    Bind address. Defaults to ``127.0.0.1`` locally; set ``0.0.0.0`` in a
    container (the bundled ``Dockerfile`` does this).
``FASTMCP_PORT``
    Bind port. Defaults to ``8000``.
``FASTMCP_PATH``
    HTTP path the MCP endpoint is served on. Defaults to ``/mcp``.
``FASTMCP_ALLOWED_HOSTS`` / ``FASTMCP_ALLOWED_ORIGINS``
    Comma-separated allowlists used for DNS-rebinding protection. Set these
    to your public hostname when deploying behind a proxy or load balancer.
"""

from __future__ import annotations

import os

from example_server.server import mcp

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_PATH = "/mcp"


def _split_env_list(name: str) -> list[str] | None:
    """Parse a comma-separated environment variable into a list.

    Returns ``None`` when unset or empty so FastMCP applies its own secure
    defaults rather than an empty allowlist.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> None:
    """Run the server over Streamable HTTP."""
    transport_kwargs: dict[str, object] = {
        "host": os.environ.get("FASTMCP_HOST", DEFAULT_HOST),
        "port": int(os.environ.get("FASTMCP_PORT", DEFAULT_PORT)),
        "path": os.environ.get("FASTMCP_PATH", DEFAULT_PATH),
    }

    allowed_hosts = _split_env_list("FASTMCP_ALLOWED_HOSTS")
    if allowed_hosts is not None:
        transport_kwargs["allowed_hosts"] = allowed_hosts

    allowed_origins = _split_env_list("FASTMCP_ALLOWED_ORIGINS")
    if allowed_origins is not None:
        transport_kwargs["allowed_origins"] = allowed_origins

    mcp.run(transport="http", **transport_kwargs)


if __name__ == "__main__":
    main()
