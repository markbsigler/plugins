#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "polars>=1.9",
#     "pydantic>=2.9",
# ]
# ///
"""Summarize a delimited table (CSV/TSV/...) with polars.

Example:
    ./table_stats.py data.csv
    ./table_stats.py data.tsv --separator '\t'

Prints one JSON object (row count and per-column name/dtype/null-count),
shaped and validated by a pydantic v2 model rather than an ad hoc dict.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl
from pydantic import BaseModel, Field


class ColumnStats(BaseModel):
    """Summary statistics for a single column."""

    name: str
    dtype: str
    null_count: int = Field(ge=0)


class TableSummary(BaseModel):
    """Summary statistics for an entire table."""

    rows: int = Field(ge=0)
    columns: list[ColumnStats]


def summarize(path: Path, separator: str) -> TableSummary:
    """Read the delimited file at ``path`` and compute its summary."""
    frame = pl.read_csv(path, separator=separator)
    null_counts = frame.null_count().row(0, named=True)
    columns = [
        ColumnStats(name=name, dtype=str(dtype), null_count=null_counts[name])
        for name, dtype in frame.schema.items()
    ]
    return TableSummary(rows=frame.height, columns=columns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to a delimited text file.")
    parser.add_argument("--separator", default=",", help="Field separator (default: ',').")
    args = parser.parse_args(argv)

    try:
        summary = summarize(args.path, args.separator)
    except (OSError, pl.exceptions.PolarsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(summary.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
