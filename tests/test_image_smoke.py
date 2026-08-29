"""Unit tests for scripts/image_smoke.py.

Every subprocess invocation, network call, and socket bind is mocked, so
these tests run in milliseconds and need no real container engine, image, or
network access. `wait_for_mcp`'s own tests are the exception where the
polling loop is exercised directly (with `time.sleep` patched to a no-op).
"""

from __future__ import annotations

import subprocess
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from discovery import REPO_ROOT as TEST_REPO_ROOT

sys.path.insert(0, str(TEST_REPO_ROOT / "scripts"))

import image_smoke


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestRun:
    """Test the `run` subprocess wrapper."""

    def test_echoes_the_command_and_delegates_to_subprocess_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(
            image_smoke.subprocess, "run", return_value=_completed(returncode=0)
        ) as run:
            result = image_smoke.run(["podman", "info"], capture=True, cwd=tmp_path)

        assert result.returncode == 0
        run.assert_called_once_with(
            ["podman", "info"], text=True, check=False, capture_output=True, cwd=tmp_path
        )
        assert "$ podman info" in capsys.readouterr().out


class TestFreePort:
    """Test `free_port` returns a real, bindable port."""

    def test_returns_a_usable_local_port(self) -> None:
        port = image_smoke.free_port()
        assert 0 < port < 65536


class TestWaitForMcp:
    """Test `wait_for_mcp`'s polling loop and exception handling."""

    def test_true_when_the_endpoint_responds_normally(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with patch.object(image_smoke.urllib.request, "urlopen", return_value=response):
            assert image_smoke.wait_for_mcp(8000, timeout=5) is True

    def test_true_when_the_endpoint_responds_with_an_http_error(self) -> None:
        error = urllib.error.HTTPError("http://x", 406, "not acceptable", Message(), None)
        with (
            patch.object(image_smoke.urllib.request, "urlopen", side_effect=error),
            patch.object(error, "close") as close,
        ):
            assert image_smoke.wait_for_mcp(8000, timeout=5) is True
        close.assert_called_once()

    def test_false_after_the_timeout_elapses_on_connection_errors(self, monkeypatch) -> None:
        # No real waiting: time.sleep is a no-op so the retry loop runs to
        # completion (bounded by the deadline check) near-instantly.
        monkeypatch.setattr(image_smoke.time, "sleep", lambda _seconds: None)
        with patch.object(
            image_smoke.urllib.request, "urlopen", side_effect=urllib.error.URLError("refused")
        ):
            assert image_smoke.wait_for_mcp(8000, timeout=0.01) is False


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """Point `image_smoke.REPO_ROOT` at a scratch directory."""
    monkeypatch.setattr(image_smoke, "REPO_ROOT", tmp_path)
    return tmp_path


def _make_dockerfile(fake_repo: Path, plugin: str, server: str) -> Path:
    dockerfile = fake_repo / plugin / "servers" / server / "Dockerfile"
    dockerfile.parent.mkdir(parents=True)
    dockerfile.write_text("FROM scratch\n")
    return dockerfile


def _dispatching_run(responses: dict[str, MagicMock]):
    """Return a `run()` replacement that dispatches on the subcommand."""

    def _fake(command: list[str], **_kwargs: object) -> MagicMock:
        subcommand = command[1]
        if subcommand in responses:
            return responses[subcommand]
        return _completed(returncode=0)

    return _fake


class TestMain:
    """Test `main`'s end-to-end control flow with every external call mocked."""

    def test_fails_when_the_engine_is_not_installed(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        del fake_repo
        with (
            patch.object(image_smoke.shutil, "which", return_value=None),
            patch.object(image_smoke, "run") as run,
        ):
            assert image_smoke.main(["p", "s", "--engine", "podman"]) == 1
        run.assert_not_called()
        assert "podman not found" in capsys.readouterr().out

    def test_fails_with_a_podman_specific_hint_when_the_engine_is_not_running(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        del fake_repo
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", return_value=_completed(returncode=1)),
        ):
            assert image_smoke.main(["p", "s", "--engine", "podman"]) == 1
        assert "podman machine start" in capsys.readouterr().out

    def test_omits_the_podman_hint_for_a_different_engine(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        del fake_repo
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/docker"),
            patch.object(image_smoke, "run", return_value=_completed(returncode=1)),
        ):
            assert image_smoke.main(["p", "s", "--engine", "docker"]) == 1
        assert "podman machine start" not in capsys.readouterr().out

    def test_fails_when_the_dockerfile_is_missing(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        del fake_repo  # only needed to point REPO_ROOT at an empty scratch dir
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", return_value=_completed(returncode=0)),
        ):
            assert image_smoke.main(["acme-tools", "acme-server"]) == 1
        assert "no Dockerfile" in capsys.readouterr().out

    def test_fails_when_the_build_fails_and_never_starts_a_container(self, fake_repo: Path) -> None:
        _make_dockerfile(fake_repo, "acme-tools", "acme-server")
        responses = {"info": _completed(returncode=0), "build": _completed(returncode=7)}
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", side_effect=_dispatching_run(responses)) as run,
        ):
            assert image_smoke.main(["acme-tools", "acme-server"]) == 7
        subcommands = [call.args[0][1] for call in run.call_args_list]
        assert "run" not in subcommands  # container was never started
        assert "rm" not in subcommands  # so nothing needed cleanup

    def test_fails_when_the_container_fails_to_start(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_dockerfile(fake_repo, "acme-tools", "acme-server")
        responses = {
            "info": _completed(returncode=0),
            "build": _completed(returncode=0),
            "run": _completed(returncode=5, stderr="boom"),
        }
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", side_effect=_dispatching_run(responses)) as run,
        ):
            assert image_smoke.main(["acme-tools", "acme-server", "--port", "9999"]) == 5
        assert "boom" in capsys.readouterr().out
        subcommands = [call.args[0][1] for call in run.call_args_list]
        assert "rm" not in subcommands  # container creation itself failed

    def test_cleans_up_and_fails_when_the_container_never_becomes_ready(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_dockerfile(fake_repo, "acme-tools", "acme-server")
        responses = {
            "info": _completed(returncode=0),
            "build": _completed(returncode=0),
            "run": _completed(returncode=0, stdout="cid-123\n"),
        }
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", side_effect=_dispatching_run(responses)) as run,
            patch.object(image_smoke, "wait_for_mcp", return_value=False),
        ):
            assert image_smoke.main(["acme-tools", "acme-server", "--port", "9999"]) == 1
        assert "did not listen on port 9999" in capsys.readouterr().out
        subcommands = [call.args[0][1] for call in run.call_args_list]
        assert "logs" in subcommands
        assert "rm" in subcommands  # cleanup still runs via `finally`
        assert subcommands[-1] == "rm"  # cleanup is always the last call

    def test_cleans_up_and_fails_when_the_mcp_probe_reports_no_tools(self, fake_repo: Path) -> None:
        _make_dockerfile(fake_repo, "acme-tools", "acme-server")
        responses = {
            "info": _completed(returncode=0),
            "build": _completed(returncode=0),
            "run": _completed(returncode=0, stdout="cid-123\n"),
        }
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", side_effect=_dispatching_run(responses)) as run,
            patch.object(image_smoke, "wait_for_mcp", return_value=True),
            patch.object(image_smoke.subprocess, "run", return_value=_completed(returncode=1)),
        ):
            assert image_smoke.main(["acme-tools", "acme-server", "--port", "9999"]) == 1
        subcommands = [call.args[0][1] for call in run.call_args_list]
        assert "logs" in subcommands
        assert subcommands[-1] == "rm"

    def test_succeeds_and_cleans_up_the_container(
        self, fake_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_dockerfile(fake_repo, "acme-tools", "acme-server")
        responses = {
            "info": _completed(returncode=0),
            "build": _completed(returncode=0),
            "run": _completed(returncode=0, stdout="cid-123\n"),
            "rm": _completed(returncode=0),
        }
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", side_effect=_dispatching_run(responses)) as run,
            patch.object(image_smoke, "wait_for_mcp", return_value=True),
            patch.object(image_smoke.subprocess, "run", return_value=_completed(returncode=0)),
        ):
            assert image_smoke.main(["acme-tools", "acme-server", "--port", "9999"]) == 0
        assert "Container smoke test passed." in capsys.readouterr().out
        rm_call = next(call for call in run.call_args_list if call.args[0][1] == "rm")
        assert "cid-123" in rm_call.args[0]

    def test_uses_free_port_when_no_port_is_specified(self, fake_repo: Path) -> None:
        _make_dockerfile(fake_repo, "acme-tools", "acme-server")
        responses = {"info": _completed(returncode=0), "build": _completed(returncode=0)}
        with (
            patch.object(image_smoke.shutil, "which", return_value="/usr/bin/podman"),
            patch.object(image_smoke, "run", side_effect=_dispatching_run(responses)) as run,
            patch.object(image_smoke, "free_port", return_value=54321),
            patch.object(image_smoke, "wait_for_mcp", return_value=False),
        ):
            image_smoke.main(["acme-tools", "acme-server"])
        start_call = next(call for call in run.call_args_list if call.args[0][1] == "run")
        assert "54321:8000" in start_call.args[0]
