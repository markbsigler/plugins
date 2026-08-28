#!/usr/bin/env python3
"""Run trivy if available, otherwise skip with a clear message.

Usage:
    just security

trivy is an optional tool: it is a Go binary with no PyPI distribution, so it
cannot be installed by `uv` on every platform. Rather than failing `just check`
on a machine without it, this reports the gap and exits 0 -- the pre-commit
hook and CI remain the enforcement points.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Entry point."""
    if not shutil.which("trivy"):
        print("trivy not installed -- skipping security scan.")
        print("  Install it with `just install`, or see")
        print("  https://trivy.dev/latest/getting-started/installation/")
        return 0

    config = REPO_ROOT / "trivy.yaml"
    result = subprocess.run(  # noqa: S603
        ["trivy", "fs", "--config", str(config), str(REPO_ROOT)],  # noqa: S607
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
