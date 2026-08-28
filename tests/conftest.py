"""Pytest hooks for the repo-level tests.

Discovery logic lives in ``discovery.py``; this module only wires it into
pytest so that any test taking a ``plugin_dir``, ``skill_dir``, or
``server_dir`` argument runs once per discovered item. Adding a new plugin
therefore requires no test edits.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from discovery import discover_plugins, discover_servers, discover_skills


def _ids(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize discovery arguments across every plugin/skill/server."""
    if "plugin_dir" in metafunc.fixturenames:
        plugins = discover_plugins()
        metafunc.parametrize("plugin_dir", plugins, ids=_ids(plugins))
    if "skill_dir" in metafunc.fixturenames:
        skills = discover_skills()
        metafunc.parametrize("skill_dir", skills, ids=_ids(skills))
    if "server_dir" in metafunc.fixturenames:
        servers = discover_servers()
        metafunc.parametrize("server_dir", servers, ids=_ids(servers))
