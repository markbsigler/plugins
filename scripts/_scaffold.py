"""Shared helpers for the plugin/server scaffolding scripts.

Both ``new_plugin.py`` and ``new_server.py`` use these so name validation and
text rewriting behave identically. Keeping them here prevents the two scripts
from drifting apart -- a mismatch previously let ``new_server.py`` accept
names that broke the whole uv workspace.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Agent Plugins v1.0.0 §5.5: 1-64 chars, lowercase alphanumeric plus hyphen
# and period, starting and ending alphanumeric, with no `--` or `..`.
PLUGIN_NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")

# Python distribution/package names cannot contain periods: a dotted name
# would become a `src/my.plugin_server/` directory, which is not importable
# and makes `[project.scripts]` invalid TOML-to-entry-point mapping.
DISTRIBUTION_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

MAX_NAME_LENGTH = 64


class InvalidNameError(ValueError):
    """Raised when a plugin or server name violates its constraints."""


def validate_plugin_name(name: str) -> None:
    """Validate a plugin name against the Agent Plugins specification.

    Raises:
        InvalidNameError: If ``name`` violates the specification.
    """
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        raise InvalidNameError(
            f"plugin name must be 1-{MAX_NAME_LENGTH} characters, got {len(name)}"
        )
    if not PLUGIN_NAME_PATTERN.match(name):
        raise InvalidNameError(
            f"{name!r} is not a valid plugin name.\n"
            "Use lowercase letters, digits, hyphens, and periods; start and end "
            "with an alphanumeric character; no '--' or '..'."
        )


def validate_server_name(name: str) -> None:
    """Validate a server name, which must also be a valid Python package name.

    Stricter than :func:`validate_plugin_name`: a server becomes a uv
    workspace member, so an invalid name breaks ``uv sync`` for *every*
    package in the repo, not just its own.

    Raises:
        InvalidNameError: If ``name`` cannot be used as a distribution name.
    """
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        raise InvalidNameError(
            f"server name must be 1-{MAX_NAME_LENGTH} characters, got {len(name)}"
        )
    if not DISTRIBUTION_NAME_PATTERN.match(name) or "--" in name:
        raise InvalidNameError(
            f"{name!r} is not a valid server name.\n"
            "Server names become Python package names: use lowercase ASCII "
            "letters, digits, and single hyphens, starting and ending with a "
            "letter or digit. Periods are not allowed."
        )


def module_name_for(server_name: str) -> str:
    """Return the importable Python module name for ``server_name``.

    Every character that is legal in a distribution name but not in a Python
    identifier is mapped to an underscore.
    """
    module = re.sub(r"[^0-9a-z]+", "_", server_name.lower())
    if not module.isidentifier():
        raise InvalidNameError(f"cannot derive a Python module name from {server_name!r}")
    return module


def default_server_name(plugin_name: str) -> str:
    """Derive a server name from a plugin name, dropping illegal characters.

    Plugin names may contain periods; server names may not, so ``acme.tools``
    yields ``acme-tools-server``.
    """
    stem = re.sub(r"[^0-9a-z]+", "-", plugin_name.lower()).strip("-")
    return f"{stem}-server"


def rewrite_text(text: str, replacements: dict[str, str]) -> str:
    """Apply ``replacements`` to ``text`` in a single pass.

    Each source region is rewritten at most once, so text produced by one
    replacement is never re-scanned by another. Applying the replacements
    sequentially instead would corrupt output whenever a replacement *value*
    contains another replacement *key* -- for example, rewriting
    ``example-server`` to ``my-example-plugin-server`` and then rewriting
    ``example-plugin`` inside the result.

    Longer keys are matched first so overlapping keys resolve unambiguously.
    """
    if not replacements:
        return text
    keys = sorted(replacements, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(key) for key in keys))
    return pattern.sub(lambda match: replacements[match.group(0)], text)


def rewrite_file(path: Path, replacements: dict[str, str]) -> None:
    """Apply :func:`rewrite_text` to a file in place, preserving LF endings."""
    original = path.read_text(encoding="utf-8")
    updated = rewrite_text(original, replacements)
    if updated != original:
        path.write_text(updated, encoding="utf-8", newline="\n")
