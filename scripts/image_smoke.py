#!/usr/bin/env python3
"""Build a server image, run it, and verify it answers MCP over HTTP.

Usage:
    just image-smoke example-plugin example-server

Cross-platform: no shell, no `trap`, no `seq`. The container is always
removed, including on failure or Ctrl-C.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTUP_TIMEOUT_SECONDS = 60

# Run in a separate `uv run` process so the container is probed with a real
# MCP client rather than a bare HTTP request.
MCP_PROBE = """
import asyncio
import sys

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:{port}/mcp") as client:
        tools = sorted(tool.name for tool in await client.list_tools())
        print("tools:", tools)
        if not tools:
            sys.exit("error: server exposed no tools")


asyncio.run(main())
"""


def run(
    command: list[str],
    *,
    capture: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command, echoing it first."""
    print(f"$ {' '.join(command)}")
    return subprocess.run(  # noqa: S603
        command,
        text=True,
        check=False,
        capture_output=capture,
        cwd=cwd,
    )


def wait_for_mcp(port: int, timeout: float) -> bool:
    """Poll the MCP endpoint until it answers, or ``timeout`` elapses.

    A bare TCP connect is *not* a usable readiness signal here: podman and
    docker publish the host port via a forwarder that binds and accepts
    connections before the process inside the container starts listening, so
    ``socket.create_connection`` succeeds immediately regardless of server
    state. Probing the actual endpoint is the only reliable gate.
    """
    deadline = time.monotonic() + timeout
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        method="GET",
        headers={"Accept": "text/event-stream"},
    )
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=2):  # noqa: S310
                return True
        except urllib.error.HTTPError:
            # The endpoint exists and is routing -- any HTTP status means the
            # ASGI app is up, even if this bare GET is not a valid MCP call.
            return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(1)
    return False


def free_port() -> int:
    """Return a currently-unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin")
    parser.add_argument("server")
    parser.add_argument("--engine", default="podman")
    parser.add_argument("--port", type=int, default=0, help="0 picks a free port.")
    parser.add_argument("--tag", default="latest")
    args = parser.parse_args(argv)

    engine = args.engine
    if not shutil.which(engine):
        print(f"error: {engine} not found. Run `just install`, or pass --engine.")
        return 1
    if run([engine, "info"], capture=True).returncode != 0:
        print(f"error: {engine} is installed but not running.")
        if engine == "podman":
            print("  start it with: podman machine start")
        return 1

    dockerfile = REPO_ROOT / args.plugin / "servers" / args.server / "Dockerfile"
    if not dockerfile.is_file():
        print(f"error: no Dockerfile at {dockerfile}")
        return 1

    image = f"{args.server}:{args.tag}"
    # `--format docker` preserves HEALTHCHECK, which the default OCI format drops.
    build = run(
        [
            engine,
            "build",
            "--format",
            "docker",
            "-f",
            str(dockerfile.relative_to(REPO_ROOT)),
            "-t",
            image,
            ".",
        ],
        cwd=REPO_ROOT,
    )
    if build.returncode != 0:
        return build.returncode

    port = args.port or free_port()
    started = run(
        [engine, "run", "-d", "-p", f"{port}:8000", image],
        capture=True,
    )
    if started.returncode != 0:
        print(started.stderr)
        return started.returncode
    container_id = started.stdout.strip()

    try:
        if not wait_for_mcp(port, STARTUP_TIMEOUT_SECONDS):
            print(
                f"error: container did not listen on port {port} within {STARTUP_TIMEOUT_SECONDS}s"
            )
            run([engine, "logs", container_id])
            return 1

        probe = MCP_PROBE.format(port=port)
        client = subprocess.run(  # noqa: S603
            ["uv", "run", "--quiet", "python", "-c", probe],  # noqa: S607
            cwd=REPO_ROOT,
            text=True,
            check=False,
        )
        if client.returncode != 0:
            run([engine, "logs", container_id])
            return client.returncode
    finally:
        run([engine, "rm", "-f", container_id], capture=True)

    print("Container smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
