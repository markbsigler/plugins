#!/usr/bin/env python3
"""Scaffold a new FastMCP server inside an existing plugin.

Usage:
    just new-server my-plugin extra-server
    uv run python scripts/new_server.py my-plugin extra-server

Copies the example server package, renames the Python module, and rewrites
identifiers so ``uv sync`` picks it up as a workspace member immediately.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_SERVER = REPO_ROOT / "my-plugin" / "servers" / "example-server"


def rewrite(path: Path, replacements: dict[str, str]) -> None:
    """Apply literal string replacements to a text file in place."""
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Create the new server package."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", help="Existing plugin directory to add the server to.")
    parser.add_argument("name", help="Name of the new server (also the directory name).")
    args = parser.parse_args(argv)

    plugin_dir = REPO_ROOT / args.plugin
    if not (plugin_dir / "plugin.json").is_file():
        sys.exit(f"error: {args.plugin} is not a plugin (no plugin.json)")

    server_name: str = args.name
    if not server_name.replace("-", "").isalnum() or server_name != server_name.lower():
        sys.exit(f"error: {server_name!r} must be lowercase alphanumeric with hyphens")

    destination = plugin_dir / "servers" / server_name
    if destination.exists():
        sys.exit(f"error: {destination} already exists")

    module = server_name.replace("-", "_")
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
        "my-plugin": args.plugin,
    }
    for path in destination.rglob("*"):
        if path.is_file():
            try:
                rewrite(path, replacements)
            except UnicodeDecodeError:
                continue

    print(f"Created {destination.relative_to(REPO_ROOT)}/")
    print()
    print("Next steps:")
    print(f"  1. Implement tools in {destination.relative_to(REPO_ROOT)}/src/{module}/server.py")
    print(f"  2. Update tests in {destination.relative_to(REPO_ROOT)}/tests/")
    print(f"  3. Add an entry to {args.plugin}/mcp.json pointing at the deployed URL")
    print("  4. uv sync && just check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
