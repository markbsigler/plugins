#!/usr/bin/env python3
"""Scaffold a new plugin by copying the ``example-plugin`` example.

Usage:
    just new-plugin acme-tools
    uv run python scripts/new_plugin.py acme-tools

Copies the template, renames the bundled server package, and rewrites the
identifiers so the result passes ``just check`` immediately -- except for the
metadata you are expected to personalise (description, author, deployed
server URL), which the manifest tests deliberately flag until you edit them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from _scaffold import (
    REPO_ROOT,
    InvalidNameError,
    default_server_name,
    module_name_for,
    rewrite_file,
    validate_plugin_name,
    validate_server_name,
)

TEMPLATE = REPO_ROOT / "example-plugin"
TEMPLATE_SERVER = "example-server"
TEMPLATE_MODULE = "example_server"
TEMPLATE_PLUGIN = "example-plugin"

# Suffixes worth rewriting. Files with no suffix (Dockerfile) are included.
TEXT_SUFFIXES = {".py", ".json", ".toml", ".md", ".txt", ".yaml", ".yml", ""}


def main(argv: list[str] | None = None) -> int:
    """Create the new plugin directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Name of the new plugin (also the directory name).")
    parser.add_argument(
        "--server-name",
        default=None,
        help="Name for the bundled MCP server (default: derived from the plugin name).",
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Omit the example MCP server (skills-only plugin).",
    )
    args = parser.parse_args(argv)

    name: str = args.name
    try:
        validate_plugin_name(name)
        server_name: str = args.server_name or default_server_name(name)
        validate_server_name(server_name)
        server_module = module_name_for(server_name)
    except InvalidNameError as exc:
        return _fail(str(exc))

    destination = REPO_ROOT / name
    if destination.exists():
        return _fail(f"{destination.relative_to(REPO_ROOT)} already exists")

    shutil.copytree(
        TEMPLATE,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "*.egg-info"),
    )

    if args.no_server:
        shutil.rmtree(destination / "servers", ignore_errors=True)
        (destination / "mcp.json").unlink(missing_ok=True)
        replacements = {TEMPLATE_PLUGIN: name}
    else:
        old_server = destination / "servers" / TEMPLATE_SERVER
        new_server = destination / "servers" / server_name
        old_server.rename(new_server)
        (new_server / "src" / TEMPLATE_MODULE).rename(new_server / "src" / server_module)
        replacements = {
            TEMPLATE_SERVER: server_name,
            TEMPLATE_MODULE: server_module,
            TEMPLATE_PLUGIN: name,
        }

    # Single pass per file: replacement output is never re-scanned, so a name
    # containing "example-plugin" cannot corrupt the generated server name.
    for path in destination.rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            try:
                rewrite_file(path, replacements)
            except UnicodeDecodeError:
                continue  # binary asset; leave untouched

    _reset_manifest(destination / "plugin.json", name)
    _print_next_steps(name, server_name, server_module, with_server=not args.no_server)
    return 0


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _reset_manifest(manifest_path: Path, name: str) -> None:
    """Clear template metadata the author must fill in."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "0.1.0"
    manifest["description"] = f"TODO: describe what {name} does."
    manifest["author"] = {"name": "TODO"}
    manifest.pop("homepage", None)
    manifest.pop("repository", None)
    manifest["keywords"] = []
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


def _print_next_steps(name: str, server: str, module: str, *, with_server: bool) -> None:
    print(f"Created {name}/")
    print()
    print("Next steps:")
    print(f"  1. Edit {name}/plugin.json      (description, author, keywords, license)")
    print(f"  2. Rename/replace skills in {name}/skills/")
    if with_server:
        print(f"  3. Edit {name}/mcp.json         (URL of your deployed server)")
        print(f"  4. Implement tools in {name}/servers/{server}/src/{module}/server.py")
        print("  5. just sync && just check")
    else:
        print("  3. just sync && just check")


if __name__ == "__main__":
    raise SystemExit(main())
