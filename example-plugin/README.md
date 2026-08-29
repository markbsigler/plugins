# example-plugin

The reference [Agent Plugin](https://agent-plugins.org/) for this repository —
copy it with `just new-plugin <name>` to start anything new. Repo-wide
conventions live in [`README.md`](../README.md) and [`AGENTS.md`](../AGENTS.md).

```text
example-plugin/
├── plugin.json                       # required portable manifest
├── mcp.json                          # streamable-http URL of the deployed server
├── skills/
│   ├── example-skill/                # stdlib-only PEP 723 script
│   │   ├── SKILL.md
│   │   └── scripts/word_count.py
│   └── table-stats/                  # polars + pydantic v2 PEP 723 script
│       ├── SKILL.md
│       └── scripts/table_stats.py
└── servers/
    └── example-server/               # FastMCP server, containerized
        ├── fastmcp.json              # canonical FastMCP config
        ├── pyproject.toml            # workspace member; deps live here
        ├── Dockerfile                # multi-stage, non-root
        ├── src/example_server/
        │   ├── server.py             # FastMCP instance + tools
        │   └── __main__.py           # transport/hosting (python -m example_server)
        └── tests/test_server.py      # in-memory Client tests
```

## What each part demonstrates

**`plugin.json`** — the closed manifest schema: required `$schema` and `name`
plus allowed metadata. Nothing else may appear at the top level.

**`skills/`** — two skill patterns. `example-skill` is stdlib-only;
`table-stats` pulls in `polars` and `pydantic` through inline
[PEP 723](https://peps.python.org/pep-0723/) metadata, so it needs no install
step and the directory stays copyable.

**`servers/example-server/`** — the FastMCP server pattern. Note the split:
`server.py` holds the `mcp` object and tools with **no transport concerns**,
which is what makes in-memory testing possible; `__main__.py` owns host/port
and reads configuration from the environment so one image runs everywhere.

**`mcp.json`** — a `streamable-http` entry. A client never launches this
server; it only connects to the `url`. You deploy the container and point the
manifest at it.

## Try it locally

```bash
# Skill scripts (uv resolves their inline dependencies on first run)
./skills/example-skill/scripts/word_count.py <<< "hello world"
./skills/table-stats/scripts/table_stats.py data.csv

# Server, from the repo root
just inspect-server example-plugin example-server        # dump the tool surface
FASTMCP_PORT=8000 uv run python -m example_server        # serve on :8000/mcp
just image-build example-plugin example-server           # build the image (podman)
just image-smoke example-plugin example-server           # build, run, verify
```

## Server configuration

`__main__.py` reads these environment variables:

| Variable | Default | Notes |
| --- | --- | --- |
| `FASTMCP_HOST` | `127.0.0.1` | The `Dockerfile` sets `0.0.0.0` |
| `FASTMCP_PORT` | `8000` | |
| `FASTMCP_PATH` | `/mcp` | |
| `FASTMCP_ALLOWED_HOSTS` | unset | Comma-separated; DNS-rebinding protection |
| `FASTMCP_ALLOWED_ORIGINS` | unset | Comma-separated |

Set the allowlists to your public hostname when deploying behind a proxy.

## Using this as a template

Prefer `just new-plugin <name>`, which does all the renaming for you. See
[Creating a plugin](../README.md#creating-a-plugin) for the full walkthrough.

## Canonical references

- Plugin package format — https://agent-plugins.org/specification
- Skill format — https://agentskills.io/specification
- MCP protocol — https://modelcontextprotocol.io/specification/
- FastMCP framework — https://gofastmcp.com/
