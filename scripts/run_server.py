#!/usr/bin/env python3
"""Run a FastMCP server directly (no container) for local development.

Usage:
    just run-server example-server
    just run-server example-server 8080

Resolves the server's Python module from its package name, so this works the
same on Windows, macOS, and Linux without shell variable munging.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_module(server: str) -> str | None:
    """Return the importable module name for a server package directory."""
    for pyproject in REPO_ROOT.glob(f"*/servers/{server}/pyproject.toml"):
        src = pyproject.parent / "src"
        for candidate in sorted(src.iterdir()) if src.is_dir() else []:
            if candidate.is_dir() and (candidate / "__init__.py").is_file():
                return candidate.name
    return None


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server", help="Server package name, e.g. example-server.")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    module = find_module(args.server)
    if module is None:
        print(f"error: no server package named {args.server!r} found under */servers/")
        return 1

    env = {**os.environ, "FASTMCP_HOST": args.host, "FASTMCP_PORT": str(args.port)}
    print(f"Serving {module} on http://{args.host}:{args.port}/mcp  (Ctrl-C to stop)")
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "--package", args.server, "python", "-m", module],  # noqa: S607
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
