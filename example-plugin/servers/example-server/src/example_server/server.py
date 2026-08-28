"""FastMCP server for the ``example-plugin`` example.

This module defines the server and its tools. It deliberately contains no
transport or hosting concerns: ``__main__`` owns those, which keeps the
``mcp`` object importable for fast in-memory tests (see ``tests/``).

References:
    FastMCP: https://gofastmcp.com/
    MCP specification: https://modelcontextprotocol.io/specification/
"""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP(
    name="example-plugin-example-server",
    instructions=(
        "Example server for the example-plugin Agent Plugin. Provides simple text "
        "utilities used to demonstrate the FastMCP server pattern."
    ),
)


@mcp.tool
def word_count(text: str) -> dict[str, int]:
    """Count the lines, words, and characters in ``text``.

    Args:
        text: The text to measure.

    Returns:
        A mapping with ``lines``, ``words``, and ``chars`` counts.
    """
    return {
        "lines": len(text.splitlines()),
        "words": len(text.split()),
        "chars": len(text),
    }


@mcp.tool
def shout(message: str) -> str:
    """Return ``message`` uppercased with a trailing exclamation mark.

    Args:
        message: The message to transform.

    Returns:
        The uppercased message.
    """
    return f"{message.upper()}!"
