"""Unit tests for scripts/run_server.py.

`subprocess.run` is mocked so these tests never actually start a server, and
`REPO_ROOT` is pointed at a scratch directory so `find_module`'s discovery
glob doesn't depend on which servers happen to exist in this repo.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from discovery import REPO_ROOT as TEST_REPO_ROOT

sys.path.insert(0, str(TEST_REPO_ROOT / "scripts"))

import run_server


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """Point `run_server.REPO_ROOT` at a scratch directory."""
    monkeypatch.setattr(run_server, "REPO_ROOT", tmp_path)
    return tmp_path


def _make_server(fake_repo: Path, plugin: str, server: str, module: str) -> None:
    server_dir = fake_repo / plugin / "servers" / server
    (server_dir / "src" / module).mkdir(parents=True)
    (server_dir / "pyproject.toml").write_text(f"[project]\nname='{server}'\n")
    (server_dir / "src" / module / "__init__.py").write_text("")


class TestFindModule:
    """Test `find_module`'s server-package discovery glob."""

    def test_finds_the_module_for_an_existing_server(self, fake_repo: Path) -> None:
        _make_server(fake_repo, "acme-tools", "acme-server", "acme_server")
        assert run_server.find_module("acme-server") == "acme_server"

    def test_returns_none_for_an_unknown_server(self, fake_repo: Path) -> None:
        del fake_repo  # only needed to point REPO_ROOT at an empty scratch dir
        assert run_server.find_module("ghost-server") is None

    def test_returns_none_when_src_directory_is_missing(self, fake_repo: Path) -> None:
        server_dir = fake_repo / "acme-tools" / "servers" / "acme-server"
        server_dir.mkdir(parents=True)
        (server_dir / "pyproject.toml").write_text("[project]\nname='acme-server'\n")
        assert run_server.find_module("acme-server") is None

    def test_returns_none_when_no_src_child_has_init_py(self, fake_repo: Path) -> None:
        server_dir = fake_repo / "acme-tools" / "servers" / "acme-server"
        (server_dir / "src" / "not_a_package").mkdir(parents=True)
        (server_dir / "pyproject.toml").write_text("[project]\nname='acme-server'\n")
        assert run_server.find_module("acme-server") is None


class TestMain:
    """Test `main`'s module resolution and subprocess invocation."""

    def test_fails_with_a_clear_message_when_the_server_is_unknown(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        del fake_repo  # only needed to point REPO_ROOT at an empty scratch dir
        with patch.object(run_server.subprocess, "run") as run:
            assert run_server.main(["ghost-server"]) == 1
        run.assert_not_called()
        assert "ghost-server" in capsys.readouterr().out

    def test_runs_the_server_via_uv_with_the_default_host_and_port(self, fake_repo: Path) -> None:
        _make_server(fake_repo, "acme-tools", "acme-server", "acme_server")
        result = MagicMock(returncode=0)
        with patch.object(run_server.subprocess, "run", return_value=result) as run:
            assert run_server.main(["acme-server"]) == 0

        command = run.call_args[0][0]
        assert command == ["uv", "run", "--package", "acme-server", "python", "-m", "acme_server"]
        env = run.call_args.kwargs["env"]
        assert env["FASTMCP_HOST"] == "127.0.0.1"
        assert env["FASTMCP_PORT"] == "8000"
        assert run.call_args.kwargs["cwd"] == fake_repo

    def test_passes_through_a_custom_host_and_port(self, fake_repo: Path) -> None:
        _make_server(fake_repo, "acme-tools", "acme-server", "acme_server")
        result = MagicMock(returncode=0)
        with patch.object(run_server.subprocess, "run", return_value=result) as run:
            assert run_server.main(["acme-server", "--port", "9000", "--host", "0.0.0.0"]) == 0  # noqa: S104

        env = run.call_args.kwargs["env"]
        assert env["FASTMCP_HOST"] == "0.0.0.0"  # noqa: S104
        assert env["FASTMCP_PORT"] == "9000"

    def test_propagates_the_subprocess_exit_code(self, fake_repo: Path) -> None:
        _make_server(fake_repo, "acme-tools", "acme-server", "acme_server")
        result = MagicMock(returncode=3)
        with patch.object(run_server.subprocess, "run", return_value=result):
            assert run_server.main(["acme-server"]) == 3
