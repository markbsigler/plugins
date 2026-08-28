"""Plugin/skill/server discovery helpers shared by the repo-level tests.

This lives outside ``conftest.py`` (hooks and fixtures only) and is
deliberately *not* imported as ``tests.discovery``: a transitive dependency
can install a top-level ``tests`` package into site-packages and shadow it.
pytest puts this directory on ``sys.path``, so ``import discovery`` is
unambiguous.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas" / "1.0.0"

# The Agent Plugins spec version this repo targets.
SPEC_VERSION = "1.0.0"
PLUGIN_SCHEMA_ID = f"https://agent-plugins.org/schemas/{SPEC_VERSION}/plugin.schema.json"
MCP_SCHEMA_ID = f"https://agent-plugins.org/schemas/{SPEC_VERSION}/mcp.schema.json"


def discover_plugins() -> list[Path]:
    """Return every plugin directory in the repo, sorted by name.

    A directory is a plugin if and only if it contains ``plugin.json`` --
    the spec's own definition -- so tooling directories never need to be
    excluded by name.
    """
    return sorted((p.parent for p in REPO_ROOT.glob("*/plugin.json")), key=lambda p: p.name)


def discover_servers() -> list[Path]:
    """Return every MCP server package directory across all plugins."""
    return sorted(
        (p.parent for p in REPO_ROOT.glob("*/servers/*/pyproject.toml")),
        key=lambda p: (p.parent.parent.name, p.name),
    )


def discover_skills() -> list[Path]:
    """Return every skill directory across all plugins."""
    return sorted(
        (p.parent for p in REPO_ROOT.glob("*/skills/*/SKILL.md")),
        key=lambda p: (p.parent.parent.name, p.name),
    )


def load_json(path: Path) -> Any:
    """Load JSON from ``path``."""
    return json.loads(path.read_text(encoding="utf-8"))
