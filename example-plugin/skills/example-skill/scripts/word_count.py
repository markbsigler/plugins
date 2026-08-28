#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Count lines, words, and characters in a file or on stdin.

Example:
    ./word_count.py notes.txt
    echo "hello world" | ./word_count.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def count_text(text: str) -> dict[str, int]:
    """Return line, word, and character counts for ``text``."""
    return {
        "lines": len(text.splitlines()),
        "words": len(text.split()),
        "chars": len(text),
    }


def read_input(path: str | None) -> str:
    """Read text from ``path``, or from stdin when ``path`` is ``None``."""
    if path is None:
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, count the input text, and print the result as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to a text file. Reads stdin when omitted.",
    )
    args = parser.parse_args(argv)

    try:
        text = read_input(args.path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(count_text(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
