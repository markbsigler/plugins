"""Integration tests that exercise the example MCP servers end-to-end.

These spawn the servers exactly as a real Agent Plugins client (or a
deployer, for the remote server) would -- via `uv run --script`, so each
script's own PEP 723 dependencies (`mcp`, `fastapi`, `uvicorn`) are resolved
by `uv` on demand and never need to be added to the repo-wide dev
environment in the root `pyproject.toml`.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from inline_snapshot import snapshot

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "my-plugin"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def _send(proc: subprocess.Popen[str], message: dict[str, object]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def test_echo_server_responds_over_stdio() -> None:
    proc = subprocess.Popen(
        ["uv", "run", "--script", "servers/echo_server.py"],
        cwd=PLUGIN_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.1"},
                },
            },
        )
        assert proc.stdout is not None
        init_line = proc.stdout.readline()
        assert init_line, proc.stderr.read() if proc.stderr else ""
        assert json.loads(init_line)["id"] == 1

        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"message": "hi"}},
            },
        )
        call_line = proc.stdout.readline()
        response = json.loads(call_line)
        text = response["result"]["content"][0]["text"]
        assert text.endswith("hi")
        assert "data_dir=" in text
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _wait_for_health(base_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:  # noqa: S310
                if resp.status == 200:
                    return
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(f"server did not become healthy in time: {last_error}")


def _post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:  # noqa: S310
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.mark.slow
def test_remote_server_serves_health_and_mcp_tool_over_http() -> None:
    port = _free_port()
    server = subprocess.Popen(
        ["uv", "run", "--script", "servers/remote_server.py"],
        cwd=PLUGIN_ROOT,
        env={**os.environ, "PORT": str(port)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_health(base_url, timeout=60)

        client_script = f"""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with streamable_http_client("{base_url}/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("add", {{"a": 2, "b": 5}})
            print(result.content[0].text)

asyncio.run(main())
"""
        result = subprocess.run(
            ["uv", "run", "--with", "mcp>=2.0", "python3", "-c", client_script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "7"

        # Pydantic v2 validates the request/response bodies for the plain
        # (non-MCP) /echo endpoint; check both the happy path and a
        # validation failure (empty message).
        status, echo_body = _post_json(f"{base_url}/echo", {"message": "hi there"})
        assert status == 200
        assert echo_body == snapshot({"message": "hi there", "length": 8})

        status, error_body = _post_json(f"{base_url}/echo", {"message": ""})
        assert status == 422
        assert error_body == snapshot(
            {
                "detail": [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "message"],
                        "msg": "String should have at least 1 character",
                        "input": "",
                        "ctx": {"min_length": 1},
                    }
                ]
            }
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
