#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.115",
#     "mcp>=2.0",
#     "pydantic>=2.9",
#     "uvicorn>=0.32",
# ]
# ///
"""Reference implementation for a remote (`streamable-http`) MCP server.

Unlike `echo_server.py`'s `stdio` transport, a conformant Agent Plugins
client never launches this process: the `mcp.json` `streamable-http` entry
only records a `url`. You deploy this yourself (locally for development,
behind HTTPS for anyone else) and point that `url` at wherever it runs.

Run it directly for local testing (set `PORT` to override the default 8000):

    ./remote_server.py                       # serves http://127.0.0.1:8000
    curl http://127.0.0.1:8000/health
    curl -X POST http://127.0.0.1:8000/echo -H 'content-type: application/json' \\
        -d '{"message": "hi"}'

FastAPI hosts the MCP SDK's Streamable HTTP ASGI app under `/mcp`, which lets
this plugin also expose ordinary HTTP endpoints (health checks, auth, request
logging, ...) alongside the MCP protocol on the same server. `/echo` shows
FastAPI's usual pattern of validating requests/responses with Pydantic v2
models, independent of anything MCP-specific.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

mcp = MCPServer("my-plugin-example-remote")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


# `session_manager` is only available after `streamable_http_app()` has been
# called at least once, so build the mounted app before referencing it below.
mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run the MCP session manager for the lifetime of the FastAPI app."""
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="my-plugin example remote MCP server", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness endpoint outside the MCP protocol, for load balancers/monitors."""
    return {"status": "ok"}


class EchoRequest(BaseModel):
    """Request body for `POST /echo`."""

    message: str = Field(min_length=1, max_length=4096)


class EchoResponse(BaseModel):
    """Response body for `POST /echo`."""

    message: str
    length: int = Field(ge=0)


@app.post("/echo")
def echo(request: EchoRequest) -> EchoResponse:
    """Echo `message` back with its length.

    A plain (non-MCP) HTTP endpoint showing FastAPI's standard
    request/response validation via Pydantic v2 models: an invalid body
    (e.g. an empty `message`) is rejected with `422` before this function
    ever runs.
    """
    return EchoResponse(message=request.message, length=len(request.message))


# `mcp_app` already serves its own route at "/mcp", so mount it at the root
# rather than under an additional "/mcp" prefix (which would otherwise
# produce "/mcp/mcp").
app.mount("/", mcp_app)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
