"""Unit tests for scripts/toolchain.py.

Every external command (subprocess.run, shutil.which) is mocked, so these
tests exercise the actual branching logic without depending on which tools
happen to be installed on the machine running pytest. That matters here in
particular: a previous bug in this module made `just install`/`doctor`
report success while the workspace was actually broken (ModuleNotFoundError
on `pytest`), and it went unnoticed because nothing tested the logic
directly -- only the real environment, which happened to be fine.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from discovery import REPO_ROOT as TEST_REPO_ROOT

sys.path.insert(0, str(TEST_REPO_ROOT / "scripts"))

import toolchain


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestToolPackageFor:
    """Test `Tool.package_for` manager-specific overrides."""

    def test_uses_the_default_name_when_no_override_exists(self) -> None:
        tool = toolchain.Tool(name="trivy", required=False, purpose="scan")
        assert tool.package_for("brew") == "trivy"

    def test_uses_the_manager_specific_override(self) -> None:
        tool = toolchain.Tool(
            name="podman", required=False, purpose="containers", package={"winget": "RedHat.Podman"}
        )
        assert tool.package_for("winget") == "RedHat.Podman"
        assert tool.package_for("brew") == "podman"


class TestDetectPackageManager:
    """Test the per-platform package manager preference order."""

    def test_returns_the_first_available_manager_for_the_platform(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.sys, "platform", "darwin")
        monkeypatch.setattr(
            toolchain.shutil, "which", lambda name: "/usr/bin/brew" if name == "brew" else None
        )
        assert toolchain.detect_package_manager() == "brew"

    def test_returns_none_when_no_manager_is_found(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.sys, "platform", "darwin")
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: None)
        assert toolchain.detect_package_manager() is None

    def test_falls_back_to_the_linux_order_for_an_unknown_platform(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.sys, "platform", "freebsd13")
        monkeypatch.setattr(
            toolchain.shutil, "which", lambda name: "/usr/bin/dnf" if name == "dnf" else None
        )
        assert toolchain.detect_package_manager() == "dnf"


class TestToolVersion:
    """Test `tool_version`'s subprocess handling and output parsing."""

    def test_reports_not_installed_when_which_finds_nothing(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: None)
        tool = toolchain.Tool(name="ghost", required=True, purpose="x")
        assert toolchain.tool_version(tool) == "not installed"

    def test_returns_the_first_line_of_version_output(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/uv")
        with patch.object(
            toolchain.subprocess, "run", return_value=_completed(stdout="uv 0.9.0\nextra\n")
        ):
            tool = toolchain.Tool(name="uv", required=True, purpose="x")
            assert toolchain.tool_version(tool) == "uv 0.9.0"

    def test_trivy_uses_quiet_version_flag_to_avoid_config_noise(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/trivy")
        with patch.object(
            toolchain.subprocess, "run", return_value=_completed(stdout="Version: 0.74\n")
        ) as run:
            tool = toolchain.Tool(name="trivy", required=False, purpose="x")
            assert toolchain.tool_version(tool) == "Version: 0.74"
        args = run.call_args[0][0]
        assert args[1:3] == ["-q", "version"]

    def test_falls_back_to_stderr_when_stdout_is_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/x")
        with patch.object(
            toolchain.subprocess, "run", return_value=_completed(stderr="error text\n")
        ):
            tool = toolchain.Tool(name="x", required=True, purpose="x")
            assert toolchain.tool_version(tool) == "error text"

    def test_reports_installed_when_output_is_completely_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/x")
        with patch.object(toolchain.subprocess, "run", return_value=_completed()):
            tool = toolchain.Tool(name="x", required=True, purpose="x")
            assert toolchain.tool_version(tool) == "installed"

    def test_handles_a_process_that_cannot_be_launched(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/x")
        with patch.object(toolchain.subprocess, "run", side_effect=OSError("boom")):
            tool = toolchain.Tool(name="x", required=True, purpose="x")
            assert toolchain.tool_version(tool) == "installed (version unknown)"


class TestContainerEngineStatus:
    """Test `container_engine_status` across install/running states."""

    def test_reports_not_installed(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: None)
        assert toolchain.container_engine_status("podman") == (False, "not installed")

    def test_reports_ready_when_info_succeeds(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/podman")
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=0)):
            assert toolchain.container_engine_status("podman") == (True, "ready")

    def test_reports_not_running_when_info_fails(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/podman")
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=1)):
            assert toolchain.container_engine_status("podman") == (
                False,
                "installed but not running",
            )

    def test_reports_not_responding_on_a_launch_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/podman")
        with patch.object(toolchain.subprocess, "run", side_effect=OSError("boom")):
            assert toolchain.container_engine_status("podman") == (
                False,
                "installed but not responding",
            )


class TestWorkspaceToolOk:
    """Test `workspace_tool_ok`'s subprocess result handling."""

    def test_true_when_the_tool_runs_successfully(self) -> None:
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=0)):
            assert toolchain.workspace_tool_ok("ruff") is True

    def test_false_on_a_nonzero_exit(self) -> None:
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=1)):
            assert toolchain.workspace_tool_ok("ruff") is False

    def test_false_when_the_process_cannot_be_launched(self) -> None:
        with patch.object(toolchain.subprocess, "run", side_effect=OSError("boom")):
            assert toolchain.workspace_tool_ok("ruff") is False


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """Point `toolchain.REPO_ROOT` at a scratch directory for these tests."""
    monkeypatch.setattr(toolchain, "REPO_ROOT", tmp_path)
    return tmp_path


class TestDiscoverServerPackages:
    """Test the `*/servers/*/pyproject.toml` discovery glob."""

    def test_finds_every_server_with_an_importable_src_package(self, fake_repo: Path) -> None:
        server = fake_repo / "acme-tools" / "servers" / "acme-server"
        pkg = server / "src" / "acme_server"
        pkg.mkdir(parents=True)
        (server / "pyproject.toml").write_text("[project]\nname='acme-server'\n")
        (pkg / "__init__.py").write_text("")

        assert toolchain.discover_server_packages() == [("acme-server", "acme_server")]

    def test_skips_a_server_with_no_src_directory(self, fake_repo: Path) -> None:
        server = fake_repo / "acme-tools" / "servers" / "acme-server"
        server.mkdir(parents=True)
        (server / "pyproject.toml").write_text("[project]\nname='acme-server'\n")

        assert toolchain.discover_server_packages() == []

    def test_skips_a_src_child_with_no_init_py(self, fake_repo: Path) -> None:
        server = fake_repo / "acme-tools" / "servers" / "acme-server"
        (server / "src" / "not_a_package").mkdir(parents=True)
        (server / "pyproject.toml").write_text("[project]\nname='acme-server'\n")

        assert toolchain.discover_server_packages() == []

    def test_returns_nothing_when_no_servers_exist(self, fake_repo: Path) -> None:
        del fake_repo  # only needed to point REPO_ROOT at an empty scratch dir
        assert toolchain.discover_server_packages() == []


class TestServerPackageImportable:
    """Test `server_package_importable`'s subprocess handling."""

    def test_true_when_the_import_succeeds(self) -> None:
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=0)):
            assert toolchain.server_package_importable("example_server") is True

    def test_false_when_the_import_fails(self) -> None:
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=1)):
            assert toolchain.server_package_importable("example_server") is False

    def test_false_when_the_process_cannot_be_launched(self) -> None:
        with patch.object(toolchain.subprocess, "run", side_effect=OSError("boom")):
            assert toolchain.server_package_importable("example_server") is False


class TestSyncWorkspace:
    """Test `sync_workspace`'s success/failure/exception paths."""

    def test_true_on_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=0)):
            assert toolchain.sync_workspace() is True
        assert "uv sync --all-packages" in capsys.readouterr().out

    def test_false_on_a_nonzero_exit(self) -> None:
        with patch.object(toolchain.subprocess, "run", return_value=_completed(returncode=1)):
            assert toolchain.sync_workspace() is False

    def test_false_when_the_process_cannot_be_launched(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(toolchain.subprocess, "run", side_effect=OSError("boom")):
            assert toolchain.sync_workspace() is False
        assert "workspace sync failed" in capsys.readouterr().out


class TestInstallTool:
    """Test `install_tool`'s uv-then-package-manager fallback order."""

    def test_prefers_uv_tool_install_when_a_pypi_package_is_declared(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/uv")
        tool = toolchain.Tool(name="just", required=True, purpose="x", uv_package="rust-just")
        with patch.object(
            toolchain.subprocess, "run", return_value=_completed(returncode=0)
        ) as run:
            assert toolchain.install_tool(tool, manager="brew") is True
        assert run.call_args[0][0] == ["uv", "tool", "install", "rust-just"]

    def test_falls_back_to_the_package_manager_when_uv_tool_install_fails(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/uv")
        tool = toolchain.Tool(name="just", required=True, purpose="x", uv_package="rust-just")
        results = iter([_completed(returncode=1), _completed(returncode=0)])
        with patch.object(
            toolchain.subprocess, "run", side_effect=lambda *_args, **_kwargs: next(results)
        ):
            assert toolchain.install_tool(tool, manager="brew") is True

    def test_uses_the_package_manager_directly_with_no_uv_package(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: None)
        tool = toolchain.Tool(name="podman", required=False, purpose="x")
        with patch.object(
            toolchain.subprocess, "run", return_value=_completed(returncode=0)
        ) as run:
            assert toolchain.install_tool(tool, manager="brew") is True
        assert run.call_args[0][0] == ["brew", "install", "podman"]

    def test_false_when_no_manager_is_available(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: None)
        tool = toolchain.Tool(name="podman", required=False, purpose="x")
        assert toolchain.install_tool(tool, manager=None) is False


class TestPrintManualInstructions:
    """Test the manual-install fallback message."""

    def test_lists_each_missing_tool_with_its_docs_link(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tools = [
            toolchain.Tool(name="trivy", required=False, purpose="x", docs="https://trivy.example")
        ]
        toolchain.print_manual_instructions(tools)
        out = capsys.readouterr().out
        assert "trivy" in out
        assert "https://trivy.example" in out


class TestDoInstall:
    """Test `do_install`'s tool-installation and workspace-sync flow."""

    def test_fails_immediately_when_uv_is_missing(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: None)
        assert toolchain.do_install() == 1
        assert "uv is required" in capsys.readouterr().out

    def test_returns_zero_when_everything_is_already_installed(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/x")
        with patch.object(toolchain, "sync_workspace", return_value=True):
            assert toolchain.do_install() == 0

    def test_installs_a_missing_optional_tool_and_continues(self, monkeypatch) -> None:
        present = {"uv"}
        monkeypatch.setattr(
            toolchain.shutil, "which", lambda name: "/x" if name in present else None
        )
        with (
            patch.object(toolchain, "install_tool", return_value=True) as install,
            patch.object(toolchain, "sync_workspace", return_value=True),
        ):
            assert toolchain.do_install() == 0
        assert install.called

    def test_fails_when_a_required_tool_cannot_be_installed(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda name: "/x" if name == "uv" else None)
        with patch.object(toolchain, "install_tool", return_value=False):
            assert toolchain.do_install() == 1

    def test_succeeds_when_only_an_optional_tool_fails_to_install(self, monkeypatch) -> None:
        # `just` (required) is present; only optional tools are missing and fail.
        present = {"uv", "just"}
        monkeypatch.setattr(
            toolchain.shutil, "which", lambda name: "/x" if name in present else None
        )
        with (
            patch.object(toolchain, "install_tool", return_value=False),
            patch.object(toolchain, "sync_workspace", return_value=True),
        ):
            assert toolchain.do_install() == 0

    def test_fails_when_the_workspace_sync_fails(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(toolchain.shutil, "which", lambda _name: "/usr/bin/x")
        with patch.object(toolchain, "sync_workspace", return_value=False):
            assert toolchain.do_install() == 1
        assert "workspace is not usable" in capsys.readouterr().out


class TestDoDoctor:
    """Test `do_doctor`'s status aggregation across every check."""

    def _patch_all_ok(self, monkeypatch) -> None:
        monkeypatch.setattr(toolchain, "tool_version", lambda _tool: "1.0.0")
        monkeypatch.setattr(toolchain, "workspace_tool_ok", lambda _name: True)
        monkeypatch.setattr(toolchain, "discover_server_packages", list)
        monkeypatch.setattr(toolchain, "container_engine_status", lambda _engine: (True, "ready"))

    def test_reports_success_when_everything_is_fine(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        assert toolchain.do_doctor("podman") == 0
        assert "All required tooling present and ready." in capsys.readouterr().out

    def test_fails_when_a_required_tool_is_missing(self, monkeypatch) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            toolchain,
            "tool_version",
            lambda tool: "not installed" if tool.required else "1.0.0",
        )
        assert toolchain.do_doctor("podman") == 1

    def test_lists_a_missing_optional_tool_without_failing(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            toolchain,
            "tool_version",
            lambda tool: "not installed" if not tool.required else "1.0.0",
        )
        assert toolchain.do_doctor("podman") == 0
        out = capsys.readouterr().out
        assert "not installed" in out
        assert "unavailable" in out

    def test_fails_when_a_workspace_tool_is_missing(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(toolchain, "workspace_tool_ok", lambda _name: False)
        assert toolchain.do_doctor("podman") == 1
        assert "run: just sync" in capsys.readouterr().out

    def test_fails_when_a_discovered_server_is_not_importable(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            toolchain, "discover_server_packages", lambda: [("acme-server", "acme_server")]
        )
        monkeypatch.setattr(toolchain, "server_package_importable", lambda _module: False)
        assert toolchain.do_doctor("podman") == 1
        out = capsys.readouterr().out
        assert "acme-server" in out
        assert "NOT INSTALLED" in out

    def test_prints_ok_for_an_importable_discovered_server(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            toolchain, "discover_server_packages", lambda: [("acme-server", "acme_server")]
        )
        monkeypatch.setattr(toolchain, "server_package_importable", lambda _module: True)
        assert toolchain.do_doctor("podman") == 0
        assert "acme-server" in capsys.readouterr().out

    def test_reports_engine_not_ready_without_failing(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            toolchain,
            "container_engine_status",
            lambda _engine: (False, "installed but not running"),
        )
        monkeypatch.setattr(
            toolchain.shutil, "which", lambda name: "/usr/bin/podman" if name == "podman" else None
        )
        assert toolchain.do_doctor("podman") == 0
        out = capsys.readouterr().out
        assert "podman machine start" in out
        assert "Start the container engine to build images." in out

    def test_suggests_krunkit_on_macos_when_podman_will_not_start(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(toolchain, "IS_MACOS", True)
        monkeypatch.setattr(
            toolchain,
            "container_engine_status",
            lambda _engine: (False, "installed but not running"),
        )
        monkeypatch.setattr(
            toolchain.shutil, "which", lambda name: "/usr/bin/podman" if name == "podman" else None
        )
        toolchain.do_doctor("podman")
        assert "krunkit" in capsys.readouterr().out

    def test_omits_the_start_hint_for_a_non_podman_engine(
        self, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            toolchain,
            "container_engine_status",
            lambda _engine: (False, "installed but not running"),
        )
        toolchain.do_doctor("docker")
        assert "podman machine start" not in capsys.readouterr().out


class TestMain:
    """Test `main`'s argument parsing and install/doctor dispatch."""

    def test_doctor_action_calls_do_doctor_with_the_given_engine(self) -> None:
        with patch.object(toolchain, "do_doctor", return_value=0) as do_doctor:
            assert toolchain.main(["doctor", "--engine", "docker"]) == 0
        do_doctor.assert_called_once_with("docker")

    def test_install_action_runs_install_then_doctor(self) -> None:
        with (
            patch.object(toolchain, "do_install", return_value=0) as do_install,
            patch.object(toolchain, "do_doctor", return_value=0) as do_doctor,
        ):
            assert toolchain.main(["install"]) == 0
        do_install.assert_called_once()
        do_doctor.assert_called_once()

    def test_install_action_short_circuits_when_install_fails(self) -> None:
        with (
            patch.object(toolchain, "do_install", return_value=1),
            patch.object(toolchain, "do_doctor") as do_doctor,
        ):
            assert toolchain.main(["install"]) == 1
        do_doctor.assert_not_called()

    def test_engine_defaults_to_podman(self) -> None:
        with patch.object(toolchain, "do_doctor", return_value=0) as do_doctor:
            toolchain.main(["doctor"])
        do_doctor.assert_called_once_with("podman")
