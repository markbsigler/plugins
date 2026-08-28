#!/usr/bin/env python3
"""Scaffold a new FastMCP server inside an existing plugin.

Usage:
    just new-server acme-tools acme-api
    uv run python scripts/new_server.py acme-tools acme-api

Copies the example server package, renames the Python module, and rewrites
identifiers so ``just sync`` picks it up as a workspace member immediately.
"""

from __future__ import annotations

import argparse
import shutil
import sys

from _scaffold import (
    REPO_ROOT,
    InvalidNameError,
    module_name_for,
    rewrite_file,
    validate_server_name,
)

TEMPLATE_SERVER = REPO_ROOT / "example-plugin" / "servers" / "example-server"


def main(argv: list[str] | None = None) -> int:
    """Create the new server package."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", help="Existing plugin directory to add the server to.")
    parser.add_argument("name", help="Name of the new server (also the directory name).")
    args = parser.parse_args(argv)

    plugin_dir = REPO_ROOT / args.plugin
    if not (plugin_dir / "plugin.json").is_file():
        return _fail(f"{args.plugin} is not a plugin (no plugin.json)")

    server_name: str = args.name
    try:
        # Stricter than plugin names: a server is a uv workspace member, so an
        # invalid name breaks `uv sync` for every package in the repo.
        validate_server_name(server_name)
        module = module_name_for(server_name)
    except InvalidNameError as exc:
        return _fail(str(exc))

    destination = plugin_dir / "servers" / server_name
    if destination.exists():
        return _fail(f"{destination.relative_to(REPO_ROOT)} already exists")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        TEMPLATE_SERVER,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "*.egg-info"),
    )
    (destination / "src" / "example_server").rename(destination / "src" / module)

    replacements = {
        "example-server": server_name,
        "example_server": module,
        "example-plugin": args.plugin,
    }
    for path in destination.rglob("*"):
        if path.is_file():
            try:
                rewrite_file(path, replacements)
            except UnicodeDecodeError:
                continue

    relative = destination.relative_to(REPO_ROOT)
    print(f"Created {relative}/")
    print()
    print("Next steps:")
    print(f"  1. Implement tools in {relative}/src/{module}/server.py")
    print(f"  2. Update tests in {relative}/tests/")
    print(f"  3. Add an entry to {args.plugin}/mcp.json pointing at the deployed URL")
    print("  4. just sync && just check")
    return 0


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
