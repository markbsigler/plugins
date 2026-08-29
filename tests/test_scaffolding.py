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
    rewrite_file,
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

    def test_rewrite_file_updates_a_file_in_place_preserving_lf(self, tmp_path: Path) -> None:
        path = tmp_path / "sample.txt"
        path.write_bytes(b"hello example-plugin\nsecond line\n")

        rewrite_file(path, {"example-plugin": "acme-tools"})

        assert path.read_bytes() == b"hello acme-tools\nsecond line\n"

    def test_rewrite_file_is_a_no_op_when_nothing_matches(self, tmp_path: Path) -> None:
        path = tmp_path / "sample.txt"
        original = b"nothing to see here\n"
        path.write_bytes(original)

        rewrite_file(path, {"example-plugin": "acme-tools"})

        assert path.read_bytes() == original


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

    def test_digit_leading_name_cannot_form_a_module_name(self) -> None:
        """`validate_server_name` allows a leading digit; Python identifiers don't.

        `module_name_for` must reject what its own regex substitution cannot
        turn into a legal module name, rather than silently emitting one.
        """
        name = "123-server"
        validate_server_name(name)  # allowed by the naming pattern...
        with pytest.raises(InvalidNameError, match="cannot derive"):
            module_name_for(name)  # ...but not a valid Python identifier


import new_plugin  # noqa: E402
import new_server  # noqa: E402


def _run_new_plugin_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke `new_plugin.py` as a real subprocess, exactly as documented."""
    return subprocess.run(  # noqa: S603
        ["uv", "run", "python", "scripts/new_plugin.py", *args],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point both scaffolding scripts' `REPO_ROOT` at a scratch directory.

    `TEMPLATE`/`TEMPLATE_SERVER` in each script are bound at import time from
    the *real* REPO_ROOT, so scaffolding still copies genuine template
    content -- only the destination moves into the scratch directory, so
    these tests run fast, in-process, and never touch the real repo.

    Every generated server's Dockerfile has a `COPY pyproject.toml uv.lock
    ./` step referencing the *workspace root*'s files (not per-server ones),
    so a minimal pair of placeholders is created here to match what a real
    uv workspace root looks like.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'scratch'\n")
    (tmp_path / "uv.lock").write_text("")
    monkeypatch.setattr(new_plugin, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(new_server, "REPO_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def scaffolded(fake_repo: Path):
    """Scaffold a plugin directly (in-process) under the scratch repo root."""
    del fake_repo  # depended on only for its REPO_ROOT monkeypatch side effect

    def _make(name: str, *extra: str) -> int:
        return new_plugin.main([name, *extra])

    return _make


def _call_main(argv: list[str]) -> int:
    """Call `new_plugin.main(argv)`, normalizing an argparse `SystemExit`.

    argparse calls `sys.exit()` directly for parse errors -- for example, a
    name starting with `-` looks like an option rather than the positional
    `name` argument -- which raises `SystemExit` through `main()` instead of
    returning an int. A subprocess invocation absorbs this into a normal
    process exit code; calling `main()` in-process does not, so both are
    normalized to the same shape here.
    """
    try:
        return new_plugin.main(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


class TestNewPluginScaffolding:
    """Test `new_plugin.main`'s scaffolding output directly, in-process."""

    def test_scaffolded_plugin_is_internally_consistent(self, fake_repo: Path, scaffolded) -> None:
        """Directory, package name, and Dockerfile COPY paths must all agree.

        Regression: a name containing `example-plugin` produced a Dockerfile
        referencing a directory that did not exist, so the image build failed.
        """
        name = "my-example-plugin"
        assert scaffolded(name) == 0

        plugin = fake_repo / name
        servers = list((plugin / "servers").iterdir())
        assert len(servers) == 1
        server = servers[0]
        assert server.name == "my-example-plugin-server"

        # pyproject name matches the directory it lives in.
        pyproject = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))
        assert pyproject["project"]["name"] == server.name

        # Every COPY source in the Dockerfile resolves to a real path.
        for line in (server / "Dockerfile").read_text(encoding="utf-8").splitlines():
            if not line.startswith("COPY ") or "--from=" in line:
                continue
            sources = line.split()[1:-1]
            for source in sources:
                assert (fake_repo / source).exists(), f"Dockerfile COPY source missing: {source}"

    def test_scaffolded_dotted_plugin_produces_importable_module(
        self, fake_repo: Path, scaffolded
    ) -> None:
        """Regression: dotted names produced `src/x.y_server/` and broke uv sync."""
        assert scaffolded("acme.tools") == 0

        server = next((fake_repo / "acme.tools" / "servers").iterdir())
        module = next(p for p in (server / "src").iterdir() if p.is_dir())
        assert module.name.isidentifier(), f"{module.name} is not importable"

        pyproject = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))
        for entry_point in pyproject["project"].get("scripts", {}).values():
            assert entry_point.split(":")[0].replace(".", "_").isidentifier()

    def test_rejects_invalid_names_without_creating_anything(self, fake_repo: Path) -> None:
        for bad in ("Bad-Name", "-leading", "has--double"):
            assert _call_main([bad]) != 0, f"{bad!r} should have been rejected"
            assert not (fake_repo / bad).exists(), f"{bad!r} left a directory behind"

    def test_fails_without_creating_anything_when_the_directory_already_exists(
        self, fake_repo: Path, scaffolded
    ) -> None:
        (fake_repo / "acme-tools").mkdir()
        assert scaffolded("acme-tools") != 0

    def test_manifest_has_todo_placeholders_and_no_template_metadata(
        self, fake_repo: Path, scaffolded
    ) -> None:
        """The template's own metadata must not leak into a new plugin."""
        name = "acme-tools"
        assert scaffolded(name) == 0

        manifest = json.loads((fake_repo / name / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == name
        assert "homepage" not in manifest
        assert "repository" not in manifest
        assert manifest["author"]["name"] == "TODO"

    def test_no_server_scaffold_has_no_server_artifacts_or_stale_docs(
        self, fake_repo: Path, scaffolded
    ) -> None:
        """`--no-server` must not leave a plugin whose docs describe deleted files.

        Regression: the template README documents servers/, mcp.json, and
        FASTMCP_* env vars throughout; rewriting it in place for a
        --no-server scaffold left stale instructions referencing a
        directory that had just been deleted.
        """
        name = "acme-tools"
        assert scaffolded(name, "--no-server") == 0

        plugin = fake_repo / name
        assert not (plugin / "servers").exists()
        assert not (plugin / "mcp.json").exists()

        readme = (plugin / "README.md").read_text(encoding="utf-8")
        for stale in ("FASTMCP_", "example-server", "example_server", "servers/example"):
            assert stale not in readme, f"README references deleted template content: {stale!r}"

    def test_custom_server_name_is_applied_throughout(self, fake_repo: Path, scaffolded) -> None:
        assert scaffolded("acme-tools", "--server-name", "acme-api") == 0
        server = fake_repo / "acme-tools" / "servers" / "acme-api"
        assert server.is_dir()
        assert (server / "src" / "acme_api").is_dir()

    def test_a_file_that_cannot_be_decoded_as_utf8_is_skipped_not_fatal(
        self, fake_repo: Path, scaffolded, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rewritable-suffix file with non-UTF-8 content must not crash the scaffold.

        `rewrite_file` opens every matching file as UTF-8 text; a stray
        binary asset with one of those suffixes must be left untouched
        rather than aborting the whole scaffold.
        """
        real_rewrite_file = new_plugin.rewrite_file

        def _raise_for_one_file(path: Path, replacements: dict[str, str]) -> None:
            if path.name == "word_count.py":
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "simulated binary content")
            real_rewrite_file(path, replacements)

        monkeypatch.setattr(new_plugin, "rewrite_file", _raise_for_one_file)
        assert scaffolded("acme-tools") == 0
        assert (fake_repo / "acme-tools" / "plugin.json").is_file()


@pytest.mark.slow
def test_new_plugin_cli_works_as_documented() -> None:
    """One real subprocess invocation, exactly as `just new-plugin` documents it.

    Everything else in this module calls `main()` directly for speed; this
    test alone verifies the actual `uv run python scripts/new_plugin.py`
    entrypoint -- shebang, argv handling, and process exit code -- works.
    """
    name = "zz-cli-smoke-probe"
    destination = REPO_ROOT / name
    try:
        result = _run_new_plugin_cli(name)
        assert result.returncode == 0, result.stderr
        assert (destination / "plugin.json").is_file()
    finally:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)


class TestNewServerScaffolding:
    """Test `new_server.main`, which previously had no test coverage at all."""

    def _make_plugin(self, fake_repo: Path, name: str = "acme-tools") -> Path:
        plugin_dir = fake_repo / name
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                    "name": name,
                }
            )
        )
        return plugin_dir

    def test_adds_a_server_package_to_an_existing_plugin(self, fake_repo: Path) -> None:
        self._make_plugin(fake_repo)
        assert new_server.main(["acme-tools", "acme-api"]) == 0

        server = fake_repo / "acme-tools" / "servers" / "acme-api"
        assert (server / "src" / "acme_api" / "server.py").is_file()
        assert (server / "src" / "acme_api" / "__main__.py").is_file()

        pyproject = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))
        assert pyproject["project"]["name"] == "acme-api"

        # Every COPY source in the Dockerfile resolves to a real path.
        for line in (server / "Dockerfile").read_text(encoding="utf-8").splitlines():
            if not line.startswith("COPY ") or "--from=" in line:
                continue
            for source in line.split()[1:-1]:
                assert (fake_repo / source).exists(), f"Dockerfile COPY source missing: {source}"

    def test_fails_when_the_target_is_not_a_plugin(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (fake_repo / "not-a-plugin").mkdir()
        assert new_server.main(["not-a-plugin", "acme-api"]) != 0
        assert not (fake_repo / "not-a-plugin" / "servers").exists()
        assert "not a plugin" in capsys.readouterr().err

    def test_rejects_an_invalid_server_name_without_creating_anything(
        self, fake_repo: Path
    ) -> None:
        self._make_plugin(fake_repo)
        assert new_server.main(["acme-tools", "Bad-Name"]) != 0
        assert not (fake_repo / "acme-tools" / "servers").exists()

    def test_fails_without_overwriting_when_the_server_already_exists(
        self, fake_repo: Path
    ) -> None:
        self._make_plugin(fake_repo)
        (fake_repo / "acme-tools" / "servers" / "acme-api").mkdir(parents=True)
        assert new_server.main(["acme-tools", "acme-api"]) != 0

    def test_a_file_that_cannot_be_decoded_as_utf8_is_skipped_not_fatal(
        self, fake_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rewritable file with non-UTF-8 content must not crash the scaffold."""
        self._make_plugin(fake_repo)
        real_rewrite_file = new_server.rewrite_file

        def _raise_for_one_file(path: Path, replacements: dict[str, str]) -> None:
            if path.name == "server.py":
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "simulated binary content")
            real_rewrite_file(path, replacements)

        monkeypatch.setattr(new_server, "rewrite_file", _raise_for_one_file)
        assert new_server.main(["acme-tools", "acme-api"]) == 0
        assert (fake_repo / "acme-tools" / "servers" / "acme-api" / "pyproject.toml").is_file()
