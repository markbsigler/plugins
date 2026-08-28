"""Validates every plugin manifest in the repo against the Agent Plugins spec.

Each test here is parametrized across *all* discovered plugins (see
``conftest.py``), so a newly added plugin directory is validated
automatically without editing this file.

Validation is layered:

1. The canonical JSON Schemas vendored in ``schemas/`` (structural truth).
2. Extra semantic rules the schema cannot express, such as the URL and
   filesystem-containment requirements in the specification prose.

The specification text at https://agent-plugins.org/specification is
authoritative where it and the schema disagree.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import jsonschema
import pytest
from discovery import (
    MCP_SCHEMA_ID,
    PLUGIN_SCHEMA_ID,
    SCHEMAS_DIR,
    discover_plugins,
    load_json,
)

# Placeholder values inherited from the my-plugin template. A real plugin must
# replace these, so we fail loudly rather than publishing "Your Name".
TEMPLATE_PLACEHOLDERS = ("Your Name", "your-org", "example.com")


def _validator(schema_name: str) -> jsonschema.protocols.Validator:
    schema = load_json(SCHEMAS_DIR / schema_name)
    return jsonschema.Draft202012Validator(schema)


def _format_errors(errors: list[jsonschema.ValidationError]) -> str:
    return "\n".join(f"  {list(e.path) or '<root>'}: {e.message}" for e in errors)


def test_repo_contains_at_least_one_plugin() -> None:
    """Guard against the discovery glob silently matching nothing."""
    assert discover_plugins(), "no */plugin.json found; discovery glob may be wrong"


def test_schema_files_are_vendored() -> None:
    assert (SCHEMAS_DIR / "plugin.schema.json").is_file()
    assert (SCHEMAS_DIR / "mcp.schema.json").is_file()


def test_plugin_json_conforms_to_canonical_schema(plugin_dir: Path) -> None:
    manifest = load_json(plugin_dir / "plugin.json")
    errors = sorted(_validator("plugin.schema.json").iter_errors(manifest), key=lambda e: e.path)
    assert not errors, f"{plugin_dir.name}/plugin.json:\n{_format_errors(errors)}"


def test_plugin_declares_the_targeted_spec_version(plugin_dir: Path) -> None:
    manifest = load_json(plugin_dir / "plugin.json")
    assert manifest["$schema"] == PLUGIN_SCHEMA_ID


def test_plugin_name_matches_directory_name(plugin_dir: Path) -> None:
    """Not required by the spec, but strongly recommended and enforced here."""
    manifest = load_json(plugin_dir / "plugin.json")
    assert manifest["name"] == plugin_dir.name, (
        f"manifest name {manifest['name']!r} should match directory {plugin_dir.name!r}"
    )


def test_plugin_metadata_has_no_unedited_template_placeholders(plugin_dir: Path) -> None:
    manifest = load_json(plugin_dir / "plugin.json")
    if manifest["name"] == "my-plugin":
        pytest.skip("my-plugin is the template itself")
    found = [
        placeholder
        for placeholder in TEMPLATE_PLACEHOLDERS
        if placeholder in str(manifest.values())
    ]
    assert not found, f"{plugin_dir.name}/plugin.json still contains template values: {found}"


def test_mcp_urls_are_not_template_placeholders(plugin_dir: Path) -> None:
    """A plugin must point at its own deployed server, not the example URL."""
    if plugin_dir.name == "my-plugin":
        pytest.skip("my-plugin is the template itself")
    mcp_path = plugin_dir / "mcp.json"
    if not mcp_path.exists():
        pytest.skip("plugin declares no MCP servers")

    for name, server in load_json(mcp_path)["mcpServers"].items():
        url = server.get("url", "")
        assert "example.com" not in url, (
            f"{plugin_dir.name}/mcp.json server {name!r} still points at the template "
            f"URL {url!r}; set it to your deployed server's URL"
        )


def test_mcp_json_conforms_to_canonical_schema(plugin_dir: Path) -> None:
    mcp_path = plugin_dir / "mcp.json"
    if not mcp_path.exists():
        pytest.skip("plugin declares no MCP servers")
    config = load_json(mcp_path)
    errors = sorted(_validator("mcp.schema.json").iter_errors(config), key=lambda e: e.path)
    assert not errors, f"{plugin_dir.name}/mcp.json:\n{_format_errors(errors)}"
    assert config["$schema"] == MCP_SCHEMA_ID


def test_mcp_remote_urls_are_absolute_https_without_userinfo_or_fragment(
    plugin_dir: Path,
) -> None:
    """Spec §7.2.1: non-loopback remote endpoints must use HTTPS."""
    mcp_path = plugin_dir / "mcp.json"
    if not mcp_path.exists():
        pytest.skip("plugin declares no MCP servers")

    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    for name, server in load_json(mcp_path)["mcpServers"].items():
        if server["type"] not in {"streamable-http", "sse"}:
            continue
        parsed = urlsplit(server["url"])
        assert parsed.scheme in {"http", "https"}, f"{name}: URL must be absolute HTTP(S)"
        assert "@" not in parsed.netloc, f"{name}: URL must not contain userinfo"
        assert parsed.fragment == "", f"{name}: URL must not contain a fragment"
        if parsed.hostname not in loopback_hosts:
            assert parsed.scheme == "https", f"{name}: non-loopback URL must use HTTPS"


def test_mcp_stdio_commands_stay_inside_the_plugin_root(plugin_dir: Path) -> None:
    """Spec §4.1: package paths must resolve within the plugin root."""
    mcp_path = plugin_dir / "mcp.json"
    if not mcp_path.exists():
        pytest.skip("plugin declares no MCP servers")

    for name, server in load_json(mcp_path)["mcpServers"].items():
        if server["type"] != "stdio":
            continue
        command = server["command"]
        if command.startswith("./"):
            resolved = (plugin_dir / command).resolve()
            assert resolved.is_relative_to(plugin_dir.resolve()), (
                f"{name}: command escapes the plugin root"
            )
            assert resolved.exists(), f"{name}: command {command!r} does not exist"


def test_mcp_headers_contain_no_obvious_secrets(plugin_dir: Path) -> None:
    """Spec §7.2.1: headers are visible package data, never a secret channel."""
    mcp_path = plugin_dir / "mcp.json"
    if not mcp_path.exists():
        pytest.skip("plugin declares no MCP servers")

    suspicious = ("authorization", "api-key", "apikey", "token", "secret", "password")
    for name, server in load_json(mcp_path)["mcpServers"].items():
        for header in server.get("headers", {}):
            assert header.lower() not in suspicious, (
                f"{name}: header {header!r} looks like a credential; "
                "authentication is client-managed in Agent Plugins v1"
            )
