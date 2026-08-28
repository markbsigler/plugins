# plugins

A collection of [Agent Plugins](https://agent-plugins.org/) — portable packages
of [Agent Skills](https://agentskills.io/specification) and
[MCP](https://modelcontextprotocol.io/specification/) servers built to the
[Agent Plugins Specification v1.0.0](https://agent-plugins.org/specification).

Every plugin lives in its own top-level directory. MCP servers are built with
[FastMCP](https://gofastmcp.com/) and deployed as containers serving Streamable
HTTP. **[`example-plugin/`](./example-plugin) is the reference example and the
pattern for every new plugin** — never hand-build one, copy it with
`just new-plugin`.

## Layout

```text
plugins/
├── example-plugin/              # ← the example and pattern for new plugins
│   ├── plugin.json              #   required portable manifest
│   ├── mcp.json                 #   streamable-http server URLs
│   ├── skills/                  #   Agent Skills (PEP 723 scripts)
│   │   ├── example-skill/
│   │   └── table-stats/
│   └── servers/
│       └── example-server/      #   FastMCP server (containerized)
│           ├── fastmcp.json
│           ├── pyproject.toml
│           ├── Dockerfile
│           ├── src/example_server/
│           └── tests/
│
├── schemas/1.0.0/               # vendored canonical Agent Plugins JSON Schemas
├── scripts/                     # new_plugin.py / new_server.py scaffolding
├── tests/                       # repo-level validation (auto-discovers plugins)
├── justfile                     # task runner — start here
├── pyproject.toml               # uv workspace root + dev tooling config
└── uv.lock                      # one lockfile for every server
```

## Quick start

```bash
git clone <this-repo> && cd plugins
just install                    # installs uv, just, podman, trivy + syncs the workspace
just install-hooks              # optional: pre-commit git hook
just check                      # lint + format + types + spelling + tests + security
```

`just install` is idempotent — re-run it any time to verify your setup.
`just doctor` reports the status of every required tool without changing
anything.

Container images are built and run with [Podman](https://podman.io/)
(rootless, daemonless). The `Dockerfile` is OCI-standard, so Docker works too:
pass `just container=docker <recipe>`.

If Podman is installed but its VM isn't running, `just doctor` will tell you —
start it with `podman machine start` (or `podman machine init` the first time).
On macOS a `libkrun` machine additionally needs `krunkit`:
`brew tap slp/krun && brew install krunkit`.

---

# Contributing a new plugin

## 1. Scaffold from the example

```bash
just new-plugin acme-tools
```

This copies `example-plugin/`, renames the bundled server package and Python module,
and rewrites every identifier. You get a complete, working plugin: manifest,
two example skills, and a containerized FastMCP server with tests.

Prefer a different server name:

```bash
just new-plugin acme-tools --server-name acme-api
```

## 2. Fill in the TODOs

The scaffold deliberately leaves markers that the test suite **fails on** until
you replace them — that is the guardrail, not a bug:

| File | What to change |
| --- | --- |
| `acme-tools/plugin.json` | `description`, `author`, `keywords`, `license` |
| `acme-tools/mcp.json` | `url` → your deployed server (the template `example.com` URL is rejected) |
| `acme-tools/skills/` | Replace/rename the example skills, or delete them |
| `acme-tools/servers/*/src/*/server.py` | Implement your tools |
| `acme-tools/README.md` | Describe your plugin |

Then install the new server into the workspace:

```bash
just sync
```

## 3. Write skills

A skill is a directory under `skills/` containing `SKILL.md` with YAML
frontmatter. `name` must match the directory name; `description` should say
both *what* it does and *when* to use it, since that is what an agent matches
against.

```markdown
---
name: acme-lookup
description: Looks up an Acme part number and returns its specifications. Use when the user mentions an Acme part, SKU, or catalog number.
---

# Acme lookup

Run the bundled script and summarize the result:

    ./scripts/lookup.py <part-number>
```

Bundled scripts are self-contained [PEP 723](https://peps.python.org/pep-0723/)
files — dependencies are declared inline and resolved by `uv`, so no install
step is needed and the skill directory stays copyable:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
```

Make them executable (`chmod +x`) — the test suite enforces this.

## 4. Write MCP servers

Servers use [FastMCP](https://gofastmcp.com/) — the canonical reference for
the framework — and implement the
[Model Context Protocol](https://modelcontextprotocol.io/specification/),
which is the canonical reference for the protocol itself.

Define tools in `server.py` and keep transport concerns in `__main__.py`, so
the `mcp` object stays importable for fast in-memory tests:

```python
from fastmcp import FastMCP

mcp = FastMCP(name="acme-server")


@mcp.tool
def lookup(part_number: str) -> dict[str, str]:
    """Look up an Acme part. The docstring becomes the tool description."""
    ...
```

Add another server to an existing plugin:

```bash
just new-server acme-tools acme-api
```

Useful during development:

```bash
just inspect-server acme-tools acme-api      # dump the tool/resource surface
just image-build acme-tools acme-api         # build the container image (podman)
just image-run acme-api                      # run it locally on :8000/mcp
just image-smoke acme-tools acme-api         # build, run, and verify over HTTP
```

### How servers and `mcp.json` relate

The server *source* lives in the plugin; the *running service* does not. A
client never launches these servers — it only reads the `url` from `mcp.json`
and connects. Deploy the container yourself, then point `mcp.json` at it:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "acme-api": {
      "type": "streamable-http",
      "url": "https://mcp.acme.example/acme-tools/mcp"
    }
  }
}
```

Three constraints worth knowing up front:

- **No placeholder expansion in `url`.** The spec does not expand `${VAR}` in
  URLs, so one manifest cannot cover dev/staging/prod.
- **No portable auth.** Agent Plugins v1 defines no OAuth or credential field;
  authentication is client-managed.
- **`headers` are visible package data.** Never put tokens there — the test
  suite rejects credential-looking header names.

## 5. Test

```bash
just test          # everything
just test-fast     # skip subprocess/network round trips
```

Server tests use FastMCP's in-memory transport — full protocol, no network, no
ports:

```python
from fastmcp import Client
from acme_server import mcp


async def test_lookup():
    async with Client(mcp) as client:
        result = await client.call_tool("lookup", {"part_number": "A-1"})
    assert result.data == {...}
```

Repo-level tests **auto-discover** every `*/plugin.json`, so your plugin is
validated against the canonical JSON Schemas, the Agent Skills spec, and this
repo's conventions with **no test edits required**.

For verbose expected values, use
[`inline-snapshot`](https://15r10nk.github.io/inline-snapshot/):
write `snapshot()`, run `just snapshot-fix`, then **review the diff** — a
passing fix means code and test agree, not that the value is correct.

## 6. Submit

```bash
just check    # must pass
```

**PR checklist**

- [ ] `just check` passes
- [ ] `plugin.json` name matches the directory name
- [ ] No TODO/template placeholders left in manifests
- [ ] `mcp.json` points at a real deployed URL (HTTPS, no credentials in headers)
- [ ] Skills have accurate `description` fields explaining *when* to use them
- [ ] Server tools have docstrings (they become tool descriptions)
- [ ] New servers have tests and a `Dockerfile`
- [ ] `uv.lock` committed if dependencies changed

---

## Toolchain

All Python tooling runs through [`uv`](https://docs.astral.sh/uv/) — no `venv`,
`pip`, `pyenv`, or `poetry`. The repo is a **uv workspace**: each server is its
own package, resolved into one root `uv.lock` so container builds are
reproducible.

| Tool | Purpose | Recipe |
| --- | --- | --- |
| [`uv`](https://docs.astral.sh/uv/) | Packaging + workspace (Rust) | `just sync` |
| [`ruff`](https://docs.astral.sh/ruff/) | Lint + format (Rust) | `just lint` / `just fmt` |
| [`ty`](https://docs.astral.sh/ty/) | Type check (Rust) | `just typecheck` |
| [`taplo`](https://taplo.tamasfe.dev/) | TOML format (Rust) | `just fmt` |
| [`typos`](https://github.com/crate-ci/typos) | Spell check (Rust) | `just spell` |
| [`pytest`](https://docs.pytest.org/) | Tests | `just test` |
| [`trivy`](https://trivy.dev/) | Vulns, secrets, misconfig (Go) | `just security` |
| [`podman`](https://podman.io/) | Container build + run (Go) | `just image-build` |
| [`just`](https://just.systems/) | Task runner (Rust) | `just --list` |
| [`pre-commit`](https://pre-commit.com/) | Git hooks | `just install-hooks` |

Run `just` to list every recipe, or `just doctor` to check your setup.
Conventions and rationale live in [`AGENTS.md`](./AGENTS.md).

## Reference

Canonical sources — prefer these over blog posts or secondary summaries:

| Topic | Canonical source |
| --- | --- |
| Plugin package format | https://agent-plugins.org/specification |
| Skill format | https://agentskills.io/specification |
| **MCP protocol** | **https://modelcontextprotocol.io/specification/** |
| **FastMCP framework** | **https://gofastmcp.com/** |
| uv workspaces | https://docs.astral.sh/uv/concepts/projects/workspaces/ |
| Podman | https://podman.io/docs |

## License

[MIT](./LICENSE)
