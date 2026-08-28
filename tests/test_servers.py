"""Validates the structure and conventions of every MCP server package.

Parametrized across all discovered servers (see ``conftest.py``). These are
repo-level *structural* checks; each server's behaviour is tested by its own
in-memory tests under ``<server>/tests/``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from discovery import load_json

FASTMCP_SCHEMA_PREFIX = "https://gofastmcp.com/public/schemas/fastmcp.json/"
REQUIRED_FILES = ("pyproject.toml", "fastmcp.json", "Dockerfile")


def _pyproject(server_dir: Path) -> dict:
    return tomllib.loads((server_dir / "pyproject.toml").read_text(encoding="utf-8"))


def test_server_has_required_files(server_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (server_dir / name).is_file()]
    assert not missing, f"{server_dir.name}: missing {missing}"


def test_server_uses_src_layout(server_dir: Path) -> None:
    src = server_dir / "src"
    assert src.is_dir(), f"{server_dir.name}: expected a src/ layout"
    packages = [p for p in src.iterdir() if p.is_dir() and (p / "__init__.py").exists()]
    assert packages, f"{server_dir.name}: no importable package under src/"


def test_server_package_name_matches_directory(server_dir: Path) -> None:
    project = _pyproject(server_dir)["project"]
    assert project["name"] == server_dir.name, (
        f"pyproject name {project['name']!r} should match directory {server_dir.name!r}"
    )


def test_server_depends_on_fastmcp(server_dir: Path) -> None:
    """Every MCP server in this repo is built on FastMCP."""
    dependencies = _pyproject(server_dir)["project"].get("dependencies", [])
    assert any(dep.startswith("fastmcp") for dep in dependencies), (
        f"{server_dir.name}: expected a fastmcp dependency, got {dependencies}"
    )


def test_server_declares_a_python_floor(server_dir: Path) -> None:
    project = _pyproject(server_dir)["project"]
    assert "requires-python" in project, f"{server_dir.name}: set requires-python"


def test_server_exposes_a_module_entrypoint(server_dir: Path) -> None:
    """``python -m <pkg>`` must work, since that is what the container runs."""
    src = server_dir / "src"
    packages = [p for p in src.iterdir() if p.is_dir() and (p / "__init__.py").exists()]
    for package in packages:
        assert (package / "__main__.py").is_file(), (
            f"{server_dir.name}: {package.name} needs a __main__.py entrypoint"
        )


def test_fastmcp_json_is_well_formed(server_dir: Path) -> None:
    config = load_json(server_dir / "fastmcp.json")
    assert config.get("$schema", "").startswith(FASTMCP_SCHEMA_PREFIX), (
        f"{server_dir.name}: fastmcp.json should reference the published schema"
    )
    assert "source" in config, "fastmcp.json requires a 'source' section"

    source_path = config["source"].get("path")
    assert source_path, "fastmcp.json source requires a 'path'"
    assert (server_dir / source_path).is_file(), (
        f"{server_dir.name}: fastmcp.json source path {source_path!r} does not exist"
    )


def test_fastmcp_json_uses_http_transport(server_dir: Path) -> None:
    """Servers here are deployed remotely over Streamable HTTP, not stdio."""
    deployment = load_json(server_dir / "fastmcp.json").get("deployment", {})
    transport = deployment.get("transport")
    if transport is None:
        pytest.skip("server does not pin a transport in fastmcp.json")
    assert transport in {"http", "streamable-http"}, (
        f"{server_dir.name}: expected an HTTP transport, got {transport!r}"
    )


def test_dockerfile_runs_as_non_root(server_dir: Path) -> None:
    dockerfile = (server_dir / "Dockerfile").read_text(encoding="utf-8")
    assert "USER " in dockerfile, (
        f"{server_dir.name}: Dockerfile must drop privileges with a USER instruction"
    )


def test_dockerfile_is_multi_stage(server_dir: Path) -> None:
    dockerfile = (server_dir / "Dockerfile").read_text(encoding="utf-8")
    from_lines = [
        line for line in dockerfile.splitlines() if line.strip().upper().startswith("FROM ")
    ]
    assert len(from_lines) >= 2, (
        f"{server_dir.name}: expected a multi-stage build to keep the runtime image small"
    )


def test_server_has_tests(server_dir: Path) -> None:
    tests_dir = server_dir / "tests"
    assert tests_dir.is_dir(), f"{server_dir.name}: add a tests/ directory"
    assert sorted(tests_dir.glob("test_*.py")), f"{server_dir.name}: no test modules found"
