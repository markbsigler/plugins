# my-plugin

An example [Agent Plugin](https://agent-plugins.org/) used as a copyable
starting point for new plugins in this repository. See the repository root
[`README.md`](../README.md) and [`AGENTS.md`](../AGENTS.md) for conventions
that apply to every plugin here.

```text
my-plugin/
├── plugin.json                  # Required portable manifest
├── mcp.json                     # Optional: portable MCP server config
├── skills/
│   ├── example-skill/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── word_count.py    # stdlib-only PEP 723 script
│   └── table-stats/
│       ├── SKILL.md
│       └── scripts/
│           └── table_stats.py   # PEP 723 script using polars + pydantic v2
└── servers/
    ├── echo_server.py           # PEP 723 stdio MCP server referenced by mcp.json
    └── remote_server.py         # PEP 723 FastAPI + pydantic v2 streamable-http MCP server
```

## What this demonstrates

- **`plugin.json`** — a manifest with the required `$schema`/`name` fields plus
  the optional metadata fields the spec allows.
- **`skills/example-skill/`** — a minimal Agent Skill whose `SKILL.md` shells
  out to a bundled, dependency-free Python script.
- **`skills/table-stats/`** — a skill that summarizes a CSV/TSV with
  [polars](https://pola.rs/), shaping and validating its JSON output with a
  [Pydantic v2](https://docs.pydantic.dev/latest/) model.
- **`mcp.json`** — one `stdio` server entry that launches a Python script via
  a plugin-relative `command` (using `${PLUGIN_ROOT}` / `${PLUGIN_DATA}`
  placeholder expansion in `env` and `cwd`), and one `streamable-http` entry
  pointing at a `url` you control.
- **`servers/echo_server.py`** — a tiny [MCP](https://modelcontextprotocol.io/)
  `stdio` server built with the Python MCP SDK, exposing one `echo` tool.
  Launched directly by a conformant client via `command` in `mcp.json`.
- **`servers/remote_server.py`** — a [FastAPI](https://fastapi.tiangolo.com/)
  app that mounts the MCP SDK's Streamable HTTP ASGI app (one `add` tool)
  alongside a plain `/health` endpoint and a `/echo` endpoint whose request
  and response bodies are validated with Pydantic v2 models. **Not** launched
  by a client — you deploy and run this yourself, then point `mcp.json`'s
  `example-remote.url` at it.

All scripts are self-contained [PEP 723](https://peps.python.org/pep-0723/)
files (inline `# /// script` metadata blocks) run through `uv run --script`
via their shebang lines, so this directory needs no separate install step to
be copied out and used standalone.

## Try it locally

```bash
# Run the skill scripts directly
./skills/example-skill/scripts/word_count.py <<< "hello world"
./skills/table-stats/scripts/table_stats.py path/to/data.csv

# Run the stdio MCP server and talk to it manually (Ctrl-D to stop)
./servers/echo_server.py

# Run the remote MCP server and try its HTTP endpoints (Ctrl-C to stop)
PORT=8000 ./servers/remote_server.py
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/echo -H 'content-type: application/json' -d '{"message": "hi"}'
```

## Using this as a template

1. Copy this directory and rename it to your plugin's name.
2. Update `name`, `version`, `description`, `author`, and other metadata in
   `plugin.json` (keep the directory name and manifest `name` identical).
3. Replace `skills/example-skill/` and `skills/table-stats/` with your own
   skill(s), or add more immediate children under `skills/`.
4. Delete `mcp.json` and `servers/` if your plugin has no MCP server, or edit
   them to describe your own server(s) — update or remove `example-remote`'s
   `url` once you deploy your own `streamable-http` server.
5. Update or extend `tests/test_schema_validation.py` (or add an equivalent)
   so your new `plugin.json`/`mcp.json` are checked against the canonical
   schemas in `../schemas/1.0.0/`.
6. Run the checks from the repo root: `just check` (or individually,
   `uv run ruff check .`, `uv run ty check .`, `uv run pytest`,
   `trivy fs --config trivy.yaml .`).
