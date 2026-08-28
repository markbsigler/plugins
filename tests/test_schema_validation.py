"""Validates plugin manifests against the canonical Agent Plugins JSON
Schemas (vendored under `schemas/`), rather than relying solely on the
hand-written structural checks in `test_my_plugin_manifest.py`.

Re-fetch `schemas/1.0.0/*.schema.json` from
https://agent-plugins.org/schemas/1.0.0/ if the Agent Plugins specification
version this repo targets changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas" / "1.0.0"
PLUGIN_ROOT = REPO_ROOT / "my-plugin"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_name: str) -> jsonschema.protocols.Validator:
    schema = _load_json(SCHEMAS_DIR / schema_name)
    return jsonschema.Draft202012Validator(schema)


def test_schema_files_are_present() -> None:
    assert (SCHEMAS_DIR / "plugin.schema.json").is_file()
    assert (SCHEMAS_DIR / "mcp.schema.json").is_file()


def test_plugin_json_conforms_to_canonical_schema() -> None:
    validator = _validator("plugin.schema.json")
    manifest = _load_json(PLUGIN_ROOT / "plugin.json")
    errors = sorted(validator.iter_errors(manifest), key=lambda e: e.path)
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_mcp_json_conforms_to_canonical_schema() -> None:
    validator = _validator("mcp.schema.json")
    mcp_config = _load_json(PLUGIN_ROOT / "mcp.json")
    errors = sorted(validator.iter_errors(mcp_config), key=lambda e: e.path)
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


@pytest.mark.parametrize(
    ("manifest", "expected_message_fragment"),
    [
        ({"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"}, "name"),
        ({"name": "my-plugin"}, "schema"),
        (
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "My-Plugin",
            },
            "does not match",
        ),
        (
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "my-plugin",
                "hooks": {},
            },
            "Additional properties",
        ),
    ],
)
def test_invalid_manifests_are_rejected_by_the_schema(
    manifest: dict[str, Any], expected_message_fragment: str
) -> None:
    validator = _validator("plugin.schema.json")
    errors = list(validator.iter_errors(manifest))
    assert errors
    assert any(expected_message_fragment in e.message for e in errors)
