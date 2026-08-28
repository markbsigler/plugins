"""Tests for the example FastMCP server.

These use FastMCP's in-memory transport: ``Client(mcp)`` speaks the full MCP
protocol directly against the server object with no network, no subprocess,
and no port juggling. That makes them fast and deterministic, and it is the
pattern every server in this repo should follow (see AGENTS.md).
"""

from __future__ import annotations

import pytest
from example_server import mcp
from fastmcp import Client


async def test_server_exposes_expected_tools() -> None:
    async with Client(mcp) as client:
        tools = sorted(tool.name for tool in await client.list_tools())
    assert tools == ["shout", "word_count"]


async def test_every_tool_has_a_description() -> None:
    """Tool descriptions come from docstrings and are shown to models."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
    missing = [tool.name for tool in tools if not (tool.description or "").strip()]
    assert not missing, f"tools missing a docstring/description: {missing}"


async def test_word_count_counts_lines_words_and_chars() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("word_count", {"text": "hello world\nsecond line"})
    assert result.data == {"lines": 2, "words": 4, "chars": 23}


async def test_word_count_handles_empty_text() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("word_count", {"text": ""})
    assert result.data == {"lines": 0, "words": 0, "chars": 0}


async def test_shout_uppercases_and_appends_bang() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("shout", {"message": "hi there"})
    assert result.data == "HI THERE!"


async def test_unknown_tool_is_rejected() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="nope"):
            await client.call_tool("nope", {})
