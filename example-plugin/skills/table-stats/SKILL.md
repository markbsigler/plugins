---
name: table-stats
description: Summarizes a CSV/TSV file's row count and per-column name, data type, and null count using polars. Use this when the user asks for a quick profile, summary, or overview of a delimited data file (CSV, TSV, etc.), such as "what's in this CSV" or "summarize this data file".
license: MIT
metadata:
  maintainer: your-org
---

# Table stats skill

This skill demonstrates using [polars](https://pola.rs/) for tabular data
processing and [Pydantic v2](https://docs.pydantic.dev/latest/) to validate
and shape the script's output, as a template for data-oriented skills in
this repository.

## When to use this skill

Use this skill when the user provides or references a delimited data file
(CSV, TSV, ...) and wants a quick structural summary: row count, column
names, inferred types, and how many nulls/missing values each column has.
This is a lightweight profile, not a statistical or visual analysis.

## How to use this skill

Run the bundled script against the file, then summarize the JSON result for
the user in plain language:

```bash
# Portable (works on macOS, Linux, and Windows)
uv run --script scripts/table_stats.py path/to/data.csv
uv run --script scripts/table_stats.py path/to/data.tsv --separator "	"

# On macOS/Linux the shebang also lets you run it directly
./scripts/table_stats.py path/to/data.csv
```

The script prints one JSON object shaped like:

```json
{"rows": 3, "columns": [{"name": "age", "dtype": "Int64", "null_count": 1}]}
```

## Notes for skill authors

- `scripts/table_stats.py` is a [PEP 723](https://peps.python.org/pep-0723/)
  script declaring `polars` and `pydantic` as inline dependencies, run via
  `uv run --script` through its shebang — no separate install step needed.
- The script validates its own output through a `pydantic.BaseModel` before
  printing it, so malformed data is caught before it reaches the caller
  rather than silently producing a bad JSON shape.
- For larger files, prefer polars' lazy API (`pl.scan_csv(...).collect()`)
  over `pl.read_csv` to avoid loading the whole file into memory.
