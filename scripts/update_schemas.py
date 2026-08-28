#!/usr/bin/env python3
"""Re-download the canonical Agent Plugins JSON Schemas.

Usage:
    just update-schemas
    just update-schemas 1.1.0

Uses urllib rather than curl so it works identically on Windows.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://agent-plugins.org/schemas"
SCHEMAS = ("plugin.schema.json", "mcp.schema.json")


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", default="1.0.0")
    args = parser.parse_args(argv)

    destination = REPO_ROOT / "schemas" / args.version
    destination.mkdir(parents=True, exist_ok=True)

    for schema in SCHEMAS:
        url = f"{BASE_URL}/{args.version}/{schema}"
        print(f"fetching {url}")
        try:
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
                if response.status != 200:
                    print(f"error: HTTP {response.status} for {url}")
                    return 1
                body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            print(f"error: could not fetch {url}: {exc}")
            return 1
        (destination / schema).write_bytes(body)

    print(f"Updated schemas/{args.version}/ -- review the diff before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
