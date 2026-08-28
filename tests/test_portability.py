"""Guards that keep the repo usable on macOS, Linux, and Windows.

These encode portability decisions that are easy to regress: a shell-specific
justfile recipe or a CRLF-committed script breaks contributors on other
platforms in ways that are confusing to diagnose.
"""

from __future__ import annotations

import re
from pathlib import Path

from discovery import REPO_ROOT

JUSTFILE = REPO_ROOT / "justfile"

# Recipe bodies are indented; comments and settings are not.
RECIPE_BODY = re.compile(r"^\s+\S")

# Constructs that only work under a POSIX shell.
POSIX_ONLY = (
    ("#!/usr/bin/env bash", "bash shebang recipe"),
    ("#!/bin/bash", "bash shebang recipe"),
    ("$(", "shell command substitution"),
    ("&&", "shell operator"),
    ("||", "shell operator"),
    (" | ", "shell pipe"),
    (">/dev/null", "POSIX device redirect"),
    ("2>&1", "POSIX fd redirect"),
    ("export ", "shell export"),
)


def _recipe_lines() -> list[tuple[int, str]]:
    """Return (line number, text) for every justfile recipe body line."""
    lines = JUSTFILE.read_text(encoding="utf-8").splitlines()
    return [
        (number, line)
        for number, line in enumerate(lines, start=1)
        if RECIPE_BODY.match(line) and not line.strip().startswith("#")
    ]


def test_justfile_recipes_avoid_posix_only_shell_constructs() -> None:
    """Recipes must run under both sh and PowerShell.

    Anything needing real logic belongs in ``scripts/*.py`` invoked via ``uv``.
    """
    offenders: list[str] = []
    for number, line in _recipe_lines():
        for construct, description in POSIX_ONLY:
            if construct in line:
                offenders.append(f"  justfile:{number}: {description} -> {line.strip()}")
    assert not offenders, (
        "justfile recipes must be shell-agnostic; move logic into scripts/*.py:\n"
        + "\n".join(offenders)
    )


def test_justfile_declares_a_windows_shell() -> None:
    content = JUSTFILE.read_text(encoding="utf-8")
    assert "set windows-shell" in content, (
        "justfile must set windows-shell so recipes work without bash on Windows"
    )


def test_helper_scripts_are_pure_python() -> None:
    """The scripts/ helpers replace shell logic, so they must not shell out to it."""
    scripts = sorted((REPO_ROOT / "scripts").glob("*.py"))
    assert scripts, "expected helper scripts under scripts/"
    offenders = [
        script.name for script in scripts if "shell=True" in script.read_text(encoding="utf-8")
    ]
    assert not offenders, f"scripts must not use shell=True: {offenders}"


def test_no_tracked_file_uses_crlf() -> None:
    """CRLF in a shebang script yields a confusing 'bad interpreter' on Unix."""
    patterns = ("*.py", "*.toml", "*.json", "*.md", "*.yaml", "*.yml")
    offenders: list[str] = []
    for pattern in patterns:
        for path in REPO_ROOT.rglob(pattern):
            if any(part in {".venv", ".git", "__pycache__"} for part in path.parts):
                continue
            if b"\r\n" in path.read_bytes():
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"files must use LF line endings (see .gitattributes): {offenders}"


def test_gitattributes_normalizes_line_endings() -> None:
    gitattributes = REPO_ROOT / ".gitattributes"
    assert gitattributes.is_file(), "add .gitattributes to pin line endings"
    content = gitattributes.read_text(encoding="utf-8")
    assert "*.py     text eol=lf" in content or "*.py text eol=lf" in content, (
        ".gitattributes must force LF for Python scripts"
    )


def test_dockerfiles_use_posix_paths(server_dir: Path) -> None:
    """Backslash paths would break builds on non-Windows engines."""
    dockerfile = server_dir / "Dockerfile"
    bad = [
        line
        for line in dockerfile.read_text(encoding="utf-8").splitlines()
        if line.startswith(("COPY ", "ADD ")) and "\\" in line.rstrip("\\")
    ]
    assert not bad, f"{server_dir.name}: Dockerfile COPY/ADD must use forward slashes: {bad}"


def test_server_entrypoint_is_platform_neutral(server_dir: Path) -> None:
    """`python -m <pkg>` works everywhere; a bare script path may not."""
    dockerfile = server_dir / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")
    cmd_lines = [line for line in content.splitlines() if line.startswith("CMD ")]
    assert cmd_lines, f"{server_dir.name}: Dockerfile needs a CMD"
    assert any("-m" in line for line in cmd_lines), (
        f'{server_dir.name}: prefer `CMD ["python", "-m", "<pkg>"]` over a script path'
    )
