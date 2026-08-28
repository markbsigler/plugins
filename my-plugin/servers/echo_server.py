#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.0"]
# ///
"""A minimal stdio MCP server exposing a single `echo` tool.

Launched by a conformant Agent Plugins client according to ``mcp.json``.
Run manually for local testing with:

    ./echo_server.py

which speaks MCP over stdio until the client (or you) closes the pipe.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("my-plugin-example-echo")


@mcp.tool()
def echo(message: str) -> str:
    """Echo ``message`` back, prefixed with the plugin data directory in use.

    Demonstrates reading a plugin-provided environment variable
    (``EXAMPLE_PLUGIN_DATA_DIR``, expanded from ``${PLUGIN_DATA}`` in
    ``mcp.json``) without writing anything to disk.
    """
    data_dir = os.environ.get("EXAMPLE_PLUGIN_DATA_DIR", "<unset>")
    return f"[data_dir={data_dir}] {message}"


if __name__ == "__main__":
    mcp.run()
