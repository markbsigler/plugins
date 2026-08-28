"""Snapshot tests for the example skill scripts' output shapes.

Uses `inline-snapshot` (https://15r10nk.github.io/inline-snapshot/) so the
expected JSON output lives right next to the assertion. Each script is
still launched via `uv run --script`, matching how a real client invokes it
and keeping the script's own dependencies (`polars`, `pydantic`) out of the
repo-wide dev environment (see AGENTS.md §3.2/§3.4).

To (re)record a snapshot after intentionally changing a script's output,
run:

    uv run pytest --inline-snapshot=fix tests/test_my_plugin_scripts.py

then review the resulting diff before committing it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from inline_snapshot import snapshot

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "my-plugin"


def test_word_count_script_reports_counts() -> None:
    result = subprocess.run(
        ["uv", "run", "--script", "skills/example-skill/scripts/word_count.py"],
        cwd=PLUGIN_ROOT,
        input="hello world\nsecond line\n",
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(result.stdout) == snapshot({"lines": 2, "words": 4, "chars": 24})


def test_table_stats_script_reports_summary(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("name,age,city\nalice,30,nyc\nbob,,sf\ncarol,25,\n", encoding="utf-8")

    result = subprocess.run(
        ["uv", "run", "--script", "skills/table-stats/scripts/table_stats.py", str(csv_path)],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
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
