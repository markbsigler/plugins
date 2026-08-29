"""Unit tests for scripts/security_scan.py.

`subprocess.run` and `shutil.which` are mocked so these tests don't depend on
whether trivy happens to be installed on the machine running pytest.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from discovery import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import security_scan


def test_skips_cleanly_when_trivy_is_not_installed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(security_scan.shutil, "which", lambda _name: None)
    assert security_scan.main() == 0
    out = capsys.readouterr().out
    assert "trivy not installed" in out
    assert "https://trivy.dev" in out


def test_runs_trivy_with_the_repo_config_and_propagates_success(monkeypatch) -> None:
    monkeypatch.setattr(security_scan.shutil, "which", lambda _name: "/usr/bin/trivy")
    result = MagicMock(returncode=0)
    with patch.object(security_scan.subprocess, "run", return_value=result) as run:
        assert security_scan.main() == 0
    args = run.call_args[0][0]
    assert args[0] == "trivy"
    assert args[1] == "fs"
    assert "--config" in args
    assert str(security_scan.REPO_ROOT / "trivy.yaml") in args
    assert str(security_scan.REPO_ROOT) in args


def test_propagates_a_nonzero_trivy_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(security_scan.shutil, "which", lambda _name: "/usr/bin/trivy")
    result = MagicMock(returncode=1)
    with patch.object(security_scan.subprocess, "run", return_value=result):
        assert security_scan.main() == 1
