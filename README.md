# plugins

A collection of [Agent Plugins](https://agent-plugins.org/) — portable
packages of Agent Skills and MCP servers built to the
[Agent Plugins Specification v1.0.0](https://agent-plugins.org/specification).
Components in this repository are implemented in Python.

Each top-level plugin directory is a self-contained package: a client should
be able to copy that one directory out of this repository and load it on its
own. Repository-wide files (this `README.md`, [`AGENTS.md`](./AGENTS.md),
`pyproject.toml`, `justfile`, `.pre-commit-config.yaml`, `schemas/`,
`tests/`) exist for development convenience and are not part of any plugin
package.

## Layout

```text
plugins/
├── AGENTS.md                # Conventions for humans and coding agents working in this repo
├── README.md                 # This file
├── pyproject.toml            # Dev tooling config (ruff, ty, pytest, inline-snapshot, jsonschema)
├── justfile                  # `just <recipe>` shortcuts for the commands below
├── .pre-commit-config.yaml   # Same checks, wired into `git commit`
├── trivy.yaml                # Security scan config (vuln, secret, misconfig)
├── .trivyignore               # Reviewed/accepted trivy findings, if any
├── schemas/1.0.0/             # Vendored canonical Agent Plugins JSON Schemas
├── tests/                     # Repo-level tests (manifest/schema checks, snapshot tests, server integration tests)
└── my-plugin/                 # An example plugin — copy this to start a new one
    ├── plugin.json
    ├── mcp.json
    ├── skills/
    │   ├── example-skill/    # stdlib-only script
    │   └── table-stats/      # polars + pydantic v2 script
    └── servers/               # A stdio server and a FastAPI + pydantic v2 streamable-http server
```

See [`my-plugin/README.md`](./my-plugin/README.md) for a walkthrough of that
example.

## Adding a new plugin

1. Copy [`my-plugin/`](./my-plugin) to a new top-level directory named after
   your plugin (see the naming rules in [`AGENTS.md`](./AGENTS.md)).
2. Update `plugin.json` and delete whichever example components you don't
   need (`skills/`, `mcp.json` + `servers/`).
3. Build out your skill(s) and/or MCP server(s), following the Python
   practices in [`AGENTS.md`](./AGENTS.md).
4. Add or update tests under [`tests/`](./tests) — including a
   schema-validation test against `schemas/1.0.0/` — and run the checks
   below.

## Development checks

This repo uses [`uv`](https://docs.astral.sh/uv/) exclusively for Python
tooling — no `venv`, `pip`, `pyenv`, or `poetry` —
[`ruff`](https://docs.astral.sh/ruff/) for linting/formatting,
[`ty`](https://docs.astral.sh/ty/) for type checking,
[`pytest`](https://docs.pytest.org/) with
[`inline-snapshot`](https://15r10nk.github.io/inline-snapshot/) for tests,
[`jsonschema`](https://python-jsonschema.readthedocs.io/) to validate
manifests against the canonical schemas, and [`trivy`](https://trivy.dev/)
for security scanning. Plugin components use
[Pydantic v2](https://docs.pydantic.dev/latest/) for data validation,
[polars](https://pola.rs/) for dataframe work, and
[FastAPI](https://fastapi.tiangolo.com/) for HTTP-based components (e.g.
remote MCP servers). [`just`](https://just.systems/) wraps all of the below
into short recipes, and the same checks also run as
[pre-commit](https://pre-commit.com/) hooks:

```bash
uv sync                            # install dev tooling into .venv
uv run ruff check .                # lint
uv run ruff format .               # format
uv run ty check .                  # type-check (repo-level code only; see AGENTS.md)
uv run pytest                      # run tests
trivy fs --config trivy.yaml .     # vulnerability / secret / misconfig scan

just check                         # ...or just run all of the above at once
uvx pre-commit install             # ...or install them as a pre-commit hook
```

## Reference

- [Agent Plugins specification](https://agent-plugins.org/specification)
- [Agent Plugins: build a plugin](https://agent-plugins.org/plugin-authors/build-an-agent-plugin)
- [Agent Skills specification](https://agentskills.io/specification)
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification)
- [Reference example plugin](https://github.com/agentplugins/agent-plugins-example)
- [uv documentation](https://docs.astral.sh/uv/)
- [ty documentation](https://docs.astral.sh/ty/)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Pydantic documentation](https://docs.pydantic.dev/latest/)
- [polars documentation](https://docs.pola.rs/)
- [inline-snapshot documentation](https://15r10nk.github.io/inline-snapshot/)
- [jsonschema documentation](https://python-jsonschema.readthedocs.io/)
- [trivy documentation](https://trivy.dev/)
- [just documentation](https://just.systems/)
- [pre-commit documentation](https://pre-commit.com/)
