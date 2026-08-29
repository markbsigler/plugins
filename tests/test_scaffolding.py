"""Regression tests for the plugin/server scaffolding.

These cover bugs that previously produced a broken plugin or, worse, broke
``uv sync`` for the *entire* workspace. Since this repo has no CI, these tests
are the only thing preventing a regression -- keep them.

The pure-function tests below are fast. The end-to-end tests that actually
scaffold into the repo root are marked ``slow``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from discovery import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _scaffold import (
    InvalidNameError,
    default_server_name,
    module_name_for,
    rewrite_text,
    validate_plugin_name,
    validate_server_name,
)


class TestSinglePassRewrite:
    """`rewrite_text` must never re-scan text it just inserted."""

    def test_replacement_output_is_not_rescanned(self) -> None:
        """Regression: sequential replace produced `my-my-example-plugin-server`.

        `example-server` -> `my-example-plugin-server` inserts a string that
        itself contains `example-plugin`; a later pass would rewrite it again.
        """
        name = "my-example-plugin"
        replacements = {
            "example-server": f"{name}-server",
            "example_server": f"{name}-server".replace("-", "_"),
            "example-plugin": name,
        }
        result = rewrite_text("example-plugin/servers/example-server/x", replacements)
        assert result == "my-example-plugin/servers/my-example-plugin-server/x"

    def test_longer_keys_win_over_shorter_overlapping_keys(self) -> None:
        replacements = {"ab": "X", "abc": "Y"}
        assert rewrite_text("abc", replacements) == "Y"

    def test_empty_replacements_is_identity(self) -> None:
        assert rewrite_text("unchanged", {}) == "unchanged"

    def test_keys_are_matched_literally_not_as_regex(self) -> None:
        assert rewrite_text("a.c", {"a.c": "ok"}) == "ok"
        assert rewrite_text("abc", {"a.c": "bad"}) == "abc"


class TestNameValidation:
    """Server names become Python packages; plugin names follow the spec."""

    @pytest.mark.parametrize("name", ["my-plugin", "acme.tools", "lint3r", "a"])
    def test_valid_plugin_names_are_accepted(self, name: str) -> None:
        validate_plugin_name(name)

    @pytest.mark.parametrize(
        "name", ["My-Plugin", "-start", "end-", "has--double", "too..many", ""]
    )
    def test_invalid_plugin_names_are_rejected(self, name: str) -> None:
        with pytest.raises(InvalidNameError):
            validate_plugin_name(name)

    @pytest.mark.parametrize("name", ["acme-server", "srv1", "a-b-c"])
    def test_valid_server_names_are_accepted(self, name: str) -> None:
        validate_server_name(name)

    @pytest.mark.parametrize(
        "name",
        [
            "foo-",  # regression: `.isalnum()` accepted this, breaking uv sync
            "-foo",
            "my.plugin",  # periods are legal in plugin names but not packages
            "has--double",
            "Foo",
            "",
        ],
    )
    def test_invalid_server_names_are_rejected(self, name: str) -> None:
        with pytest.raises(InvalidNameError):
            validate_server_name(name)

    def test_dotted_plugin_name_yields_a_legal_server_and_module(self) -> None:
        """Regression: `acme.tools` produced `src/acme.tools_server/`."""
        server = default_server_name("acme.tools")
        assert server == "acme-tools-server"
        validate_server_name(server)
        assert module_name_for(server).isidentifier()

    @pytest.mark.parametrize("name", ["a-b", "acme-tools-server", "x1-y2"])
    def test_module_names_are_always_valid_identifiers(self, name: str) -> None:
        assert module_name_for(name).isidentifier()


def _run_scaffold(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "python", *args],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


@pytest.fixture
def scaffolded():
    """Scaffold a plugin and always remove it afterwards."""
    created: list[Path] = []

    def _make(name: str, *extra: str) -> subprocess.CompletedProcess[str]:
        created.append(REPO_ROOT / name)
        return _run_scaffold("scripts/new_plugin.py", name, *extra)

    yield _make

    for path in created:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.slow
def test_scaffolded_plugin_is_internally_consistent(scaffolded) -> None:
    """Directory, package name, and Dockerfile COPY paths must all agree.

    Regression: a name containing `example-plugin` produced a Dockerfile
    referencing a directory that did not exist, so the image build failed.
    """
    name = "zz-example-plugin-probe"
    result = scaffolded(name)
    assert result.returncode == 0, result.stderr

    plugin = REPO_ROOT / name
    servers = list((plugin / "servers").iterdir())
    assert len(servers) == 1
    server = servers[0]

    # pyproject name matches the directory it lives in.
    pyproject = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["name"] == server.name

    # Every COPY source in the Dockerfile resolves to a real path.
    for line in (server / "Dockerfile").read_text(encoding="utf-8").splitlines():
        if not line.startswith("COPY ") or "--from=" in line:
            continue
        sources = line.split()[1:-1]
        for source in sources:
            assert (REPO_ROOT / source).exists(), f"Dockerfile COPY source missing: {source}"


@pytest.mark.slow
def test_scaffolded_dotted_plugin_produces_importable_module(scaffolded) -> None:
    """Regression: dotted names produced `src/x.y_server/` and broke uv sync."""
    result = scaffolded("zz.probe")
    assert result.returncode == 0, result.stderr

    server = next((REPO_ROOT / "zz.probe" / "servers").iterdir())
    module = next(p for p in (server / "src").iterdir() if p.is_dir())
    assert module.name.isidentifier(), f"{module.name} is not importable"

    pyproject = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))
    for entry_point in pyproject["project"].get("scripts", {}).values():
        assert entry_point.split(":")[0].replace(".", "_").isidentifier()


@pytest.mark.slow
def test_scaffolding_rejects_invalid_names_without_creating_anything() -> None:
    for bad in ("Bad-Name", "-leading", "has--double"):
        result = _run_scaffold("scripts/new_plugin.py", bad)
        assert result.returncode != 0, f"{bad!r} should have been rejected"
        assert not (REPO_ROOT / bad).exists(), f"{bad!r} left a directory behind"


@pytest.mark.slow
def test_scaffolded_manifest_has_todo_placeholders(scaffolded) -> None:
    """The template's own metadata must not leak into a new plugin."""
    name = "zz-manifest-probe"
    assert scaffolded(name).returncode == 0

    manifest = json.loads((REPO_ROOT / name / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == name
    assert "homepage" not in manifest
    assert "repository" not in manifest
    assert manifest["author"]["name"] == "TODO"


@pytest.mark.slow
def test_no_server_scaffold_has_no_server_artifacts_or_stale_docs(scaffolded) -> None:
    """`--no-server` must not leave a plugin whose docs describe deleted files.

    Regression: the template README documents servers/, mcp.json, and
    FASTMCP_* env vars throughout; rewriting it in place for a --no-server
    scaffold left stale instructions referencing a directory that had just
    been deleted.
    """
    name = "zz-noserver-probe"
    result = scaffolded(name, "--no-server")
    assert result.returncode == 0, result.stderr

    plugin = REPO_ROOT / name
    assert not (plugin / "servers").exists()
    assert not (plugin / "mcp.json").exists()

    readme = (plugin / "README.md").read_text(encoding="utf-8")
    for stale in ("FASTMCP_", "example-server", "example_server", "servers/example"):
        assert stale not in readme, f"README references deleted template content: {stale!r}"
