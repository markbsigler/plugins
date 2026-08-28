#!/usr/bin/env python3
"""Scaffold a new plugin by copying the ``example-plugin`` example.

Usage:
    just new-plugin my-new-plugin
    uv run python scripts/new_plugin.py my-new-plugin

Copies the template, renames the bundled server package, and rewrites the
identifiers so the result passes ``just check`` immediately -- except for the
metadata you are expected to personalise (author, homepage, repository),
which the manifest tests deliberately flag until you edit them.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "example-plugin"

# Agent Plugins v1.0.0 §5.5 name constraints.
NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
MAX_NAME_LENGTH = 64


def validate_name(name: str) -> None:
    """Exit with a helpful message if ``name`` violates the spec."""
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        sys.exit(f"error: plugin name must be 1-{MAX_NAME_LENGTH} characters")
    if not NAME_PATTERN.match(name):
        sys.exit(
            f"error: {name!r} is not a valid plugin name.\n"
            "Use lowercase letters, digits, hyphens, and periods; start and end "
            "with an alphanumeric character; no '--' or '..'."
        )


def rewrite(path: Path, replacements: dict[str, str]) -> None:
    """Apply literal string replacements to a text file in place."""
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Create the new plugin directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Name of the new plugin (also the directory name).")
    parser.add_argument(
        "--server-name",
        default=None,
        help="Name for the bundled MCP server (default: <name>-server).",
    )
    args = parser.parse_args(argv)

    name: str = args.name
    validate_name(name)

    destination = REPO_ROOT / name
    if destination.exists():
        sys.exit(f"error: {destination} already exists")

    server_name: str = args.server_name or f"{name}-server"
    validate_name(server_name)
    server_module = server_name.replace("-", "_")

    shutil.copytree(
        TEMPLATE,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "*.egg-info"),
    )

    # Rename the bundled server package directory and its Python module.
    old_server = destination / "servers" / "example-server"
    new_server = destination / "servers" / server_name
    old_server.rename(new_server)
    (new_server / "src" / "example_server").rename(new_server / "src" / server_module)

    replacements = {
        "example-server": server_name,
        "example_server": server_module,
        "example-plugin": name,
    }
    for path in destination.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".json", ".toml", ".md", ""}:
            try:
                rewrite(path, replacements)
            except UnicodeDecodeError:
                continue  # binary asset; leave untouched

    # Reset version and clear template metadata the author must fill in.
    manifest_path = destination / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "0.1.0"
    manifest["description"] = f"TODO: describe what {name} does."
    manifest["author"] = {"name": "TODO"}
    manifest.pop("homepage", None)
    manifest.pop("repository", None)
    manifest["keywords"] = []
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Created {destination.relative_to(REPO_ROOT)}/")
    print()
    print("Next steps:")
    print(f"  1. Edit {name}/plugin.json      (description, author, keywords, license)")
    print(f"  2. Edit {name}/mcp.json         (deployed server URL, or delete if none)")
    print(f"  3. Rename/replace skills in {name}/skills/")
    print(f"  4. Implement tools in {name}/servers/{server_name}/src/{server_module}/server.py")
    print("  5. just sync && just check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
