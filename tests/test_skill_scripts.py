"""Tests for skill scripts bundled with plugins.

Two layers:

1. A generic, discovery-driven smoke test that every bundled script across
   every plugin starts and responds to ``--help``. New skills get this for
   free.
2. Behaviour tests for specific scripts, using ``inline-snapshot`` so the
   expected JSON lives beside the assertion.

Scripts are launched via ``uv run --script`` exactly as a client would, so
their PEP 723 dependencies resolve without polluting the dev environment.

To re-record a snapshot after an intentional change:

    uv run pytest --inline-snapshot=fix tests/test_skill_scripts.py

then review the diff before committing it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from discovery import REPO_ROOT, discover_skills
from inline_snapshot import snapshot

# `uv` is resolved from PATH on purpose: it is this repo's required toolchain
# (see AGENTS.md) and every argument below is a repo-controlled literal, never
# user input.
UV = "uv"


def _run_script(
    script: Path, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [UV, "run", "--script", str(script), *args],
        cwd=REPO_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


def _skill_scripts() -> list[Path]:
    return [script for skill in discover_skills() for script in sorted(skill.glob("scripts/*.py"))]


@pytest.mark.slow
@pytest.mark.parametrize(
    "script",
    _skill_scripts(),
    ids=lambda p: f"{p.parent.parent.name}/{p.name}",
)
def test_every_skill_script_responds_to_help(script: Path) -> None:
    """Every bundled script must expose a working ``--help``."""
    result = _run_script(script, "--help")
    assert result.stdout.strip(), f"{script.name} produced no --help output"


@pytest.mark.slow
def test_word_count_script_reports_counts() -> None:
    script = REPO_ROOT / "example-plugin/skills/example-skill/scripts/word_count.py"
    result = _run_script(script, stdin="hello world\nsecond line\n")
    assert json.loads(result.stdout) == snapshot({"lines": 2, "words": 4, "chars": 24})


@pytest.mark.slow
def test_table_stats_script_reports_summary(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("name,age,city\nalice,30,nyc\nbob,,sf\ncarol,25,\n", encoding="utf-8")

    script = REPO_ROOT / "example-plugin/skills/table-stats/scripts/table_stats.py"
    result = _run_script(script, str(csv_path))
    assert json.loads(result.stdout) == snapshot(
        {
            "rows": 3,
            "columns": [
                {"name": "name", "dtype": "String", "null_count": 0},
                {"name": "age", "dtype": "Int64", "null_count": 1},
                {"name": "city", "dtype": "String", "null_count": 1},
            ],
        }
    )
