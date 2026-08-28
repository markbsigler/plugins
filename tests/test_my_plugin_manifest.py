"""Structural checks for the `my-plugin` example scaffold.

These are lightweight, dependency-free checks (not a full JSON Schema
validator) that catch the most common Agent Plugins manifest mistakes
directly in CI: missing required fields, an invalid `name`, and
`mcp.json` entries that violate the closed schema. For authoritative
validation, check a manifest against the canonical schemas published at
https://agent-plugins.org/schemas/1.0.0/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "my-plugin"

# Mirrors the Agent Plugins v1.0.0 §5.5 name constraints.
NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")


def _load_json(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def test_plugin_json_exists_and_is_valid_json() -> None:
    manifest_path = PLUGIN_ROOT / "plugin.json"
    assert manifest_path.is_file()
    manifest = _load_json(manifest_path)
    assert isinstance(manifest, dict)


def test_plugin_json_has_required_fields() -> None:
    manifest = _load_json(PLUGIN_ROOT / "plugin.json")
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert isinstance(manifest["name"], str) and manifest["name"]


def test_plugin_json_top_level_fields_are_known() -> None:
    allowed = {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
    manifest = _load_json(PLUGIN_ROOT / "plugin.json")
    assert set(manifest.keys()) <= allowed


def test_plugin_name_satisfies_naming_constraints() -> None:
    manifest = _load_json(PLUGIN_ROOT / "plugin.json")
    name = manifest["name"]
    assert 1 <= len(name) <= 64
    assert NAME_PATTERN.match(name), f"{name!r} violates the plugin name constraints"
    assert "--" not in name
    assert ".." not in name


def test_skill_directories_have_a_skill_md_file() -> None:
    skills_dir = PLUGIN_ROOT / "skills"
    assert skills_dir.is_dir()
    skill_dirs = [p for p in skills_dir.iterdir() if p.is_dir()]
    assert skill_dirs, "expected at least one example skill"
    for skill_dir in skill_dirs:
        assert (skill_dir / "SKILL.md").is_file()


def test_skill_frontmatter_has_required_fields() -> None:
    skills_dir = PLUGIN_ROOT / "skills"
    skill_dirs = [p for p in skills_dir.iterdir() if p.is_dir()]
    for skill_dir in skill_dirs:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n")
        frontmatter = text.split("---\n", 2)[1]
        assert f"name: {skill_dir.name}" in frontmatter
        assert "description:" in frontmatter


def test_mcp_json_has_only_allowed_top_level_fields() -> None:
    mcp_config = _load_json(PLUGIN_ROOT / "mcp.json")
    assert set(mcp_config.keys()) == {"$schema", "mcpServers"}
    assert mcp_config["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"


def test_mcp_json_stdio_command_is_plugin_relative() -> None:
    mcp_config = _load_json(PLUGIN_ROOT / "mcp.json")
    for server in mcp_config["mcpServers"].values():
        if server["type"] == "stdio":
            command = server["command"]
            assert command.startswith("./"), f"{command!r} must be a bare name or start with ./"
            assert (PLUGIN_ROOT / command).resolve().is_relative_to(PLUGIN_ROOT.resolve())


def test_mcp_json_remote_urls_are_absolute_https_without_userinfo_or_fragment() -> None:
    mcp_config = _load_json(PLUGIN_ROOT / "mcp.json")
    for server in mcp_config["mcpServers"].values():
        if server["type"] in {"streamable-http", "sse"}:
            parsed = urlsplit(server["url"])
            assert parsed.scheme == "https", "non-loopback remote MCP URLs must use HTTPS"
            assert "@" not in parsed.netloc, "remote MCP URLs must not contain userinfo"
            assert parsed.fragment == "", "remote MCP URLs must not contain a fragment"
