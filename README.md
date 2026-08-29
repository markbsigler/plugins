<div align="center">

# Agent Plugins Collection

*Portable Agent Skills and FastMCP servers, built to the Agent Plugins specification*

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Agent Plugins spec](https://img.shields.io/badge/Agent%20Plugins-v1.0.0-6f42c1?style=flat-square)](https://agent-plugins.org/specification)
[![FastMCP](https://img.shields.io/badge/servers-FastMCP-ff7000?style=flat-square)](https://gofastmcp.com/)
[![uv](https://img.shields.io/badge/tooling-uv-de5fe9?style=flat-square)](https://docs.astral.sh/uv/)

[Overview](#overview) • [Using a plugin](#using-a-plugin) • [Quick start](#quick-start) • [Creating a plugin](#creating-a-plugin) • [Reference](#reference)

</div>

A collection of [Agent Plugins](https://agent-plugins.org/) — portable packages of
[Agent Skills](https://agentskills.io/specification) and MCP servers, built to the
[Agent Plugins Specification v1.0.0](https://agent-plugins.org/specification). Every
plugin lives in its own top-level directory, and
**[`example-plugin/`](./example-plugin) is the reference pattern for every new one**.

## Overview

An Agent Plugin is a portable package that an AI agent client can load: a manifest,
some [Agent Skills](https://agentskills.io/specification), and a pointer to any
[MCP](https://modelcontextprotocol.io/specification/) servers it depends on. This repo
is a *collection* of them, plus the tooling to build, validate, and ship new ones
consistently.

MCP servers in this collection are built with [FastMCP](https://gofastmcp.com/) and
deployed as containers serving Streamable HTTP — never launched by the client, only
connected to.

> [!TIP]
> Never hand-build a plugin. Copy the pattern with `just new-plugin <name>` — see
> [Creating a plugin](#creating-a-plugin).

## Features

- **One reference pattern** — [`example-plugin/`](./example-plugin) demonstrates every
  supported component; `just new-plugin` and `just new-server` scaffold new plugins
  and servers from it with correct naming, wiring, and no manual bookkeeping.
- **Automatic validation** — the test suite discovers every `plugin.json`, skill, and
  server in the repo and validates it against the canonical
  [Agent Plugins](https://agent-plugins.org/specification) and
  [Agent Skills](https://agentskills.io/specification) schemas. Add a plugin; it's
  covered with no test edits required.
- **FastMCP servers, container-first** — each server is a `uv` workspace member with
  its own `pyproject.toml`, a multi-stage non-root `Dockerfile`, and in-memory tests
  using FastMCP's `Client` (no network, no ports).
- **Cross-platform toolchain** — `uv` is the only hard prerequisite; every other tool
  installs from PyPI or your platform's package manager. Recipes run identically on
  macOS, Linux, and Windows.
- **Security scanning built in** — [`trivy`](https://trivy.dev/) checks manifests,
  lockfiles, and Dockerfiles for vulnerabilities, secrets, and misconfigurations.

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

## Using a plugin

Agent Plugins are consumed by a **client** (an AI agent tool that implements the
[Agent Plugins specification](https://agent-plugins.org/specification)), not installed
like a package. Each plugin directory in this repo *is* the distributable unit: copy it
to wherever your client discovers plugins.

```bash
git clone https://github.com/markbsigler/plugins.git
cp -r plugins/example-plugin /path/to/your/client/plugins/
```

The client reads three things and ignores everything else:

| Path | What the client does with it |
| --- | --- |
| `plugin.json` | Identity and metadata — required |
| `skills/*/SKILL.md` | Loads each skill so the agent can invoke it |
| `mcp.json` | Connects to the MCP servers listed there |

> [!NOTE]
> `servers/` is **build-time source**, not a portable component — clients ignore it.
> It lives here so a plugin and the server it depends on stay versioned together; see
> [Deploying a plugin's server](#deploying-a-plugins-server).

### Deploying a plugin's server

Because `mcp.json` records a `url`, the server must already be running somewhere your
client can reach before the plugin is useful:

```bash
just image-build example-plugin example-server   # build the container
# push to your registry and deploy it, then:
# set that URL in example-plugin/mcp.json
```

> [!IMPORTANT]
> The spec does not expand `${VAR}` in `url`, so one manifest cannot serve dev,
> staging, and production. It also defines no portable auth field — authentication is
> client-managed, and `headers` in `mcp.json` are visible package data, so credentials
> must never go there.

## Quick start

**The only prerequisite is [`uv`](https://docs.astral.sh/uv/)** — it bootstraps
everything else, including `just`.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then, on any platform:

```bash
git clone https://github.com/markbsigler/plugins.git && cd plugins
uv tool install rust-just     # installs `just` from PyPI (all platforms)
just install                  # installs remaining tools + syncs the workspace
just check                    # lint + format + types + spelling + tests + security
```

`just install` is idempotent — re-run it any time. `just doctor` reports the status of
every tool without changing anything, and is the first thing to run when something
misbehaves.

### Platform support

Everything here runs on **macOS, Linux, and Windows**. Recipes contain no
shell-specific logic: anything needing real logic lives in `scripts/*.py` and runs
through `uv`, and `tests/test_portability.py` enforces that.

| Tool | Required? | How it installs |
| --- | --- | --- |
| `uv` | **Required** | Official installer (above); cannot self-install |
| `just` | **Required** | `uv tool install rust-just` — works on all platforms |
| `ruff`, `ty`, `taplo`, `typos`, `pytest` | **Required** | `just sync` (uv workspace) |
| `podman` | Optional | `just install`, or your package manager |
| `trivy` | Optional | `just install`, or your package manager |

`podman` and `trivy` are optional: without them you can still develop, test, and lint.
`just security` skips cleanly if `trivy` is absent, and only the container recipes need
`podman`.

`just install` detects your package manager — Homebrew, apt, dnf, pacman, zypper,
winget, scoop, or Chocolatey — and prints manual instructions if it can't find one.

Container images are built with [Podman](https://podman.io/) (rootless, daemonless).
The `Dockerfile` is OCI-standard, so Docker works too: pass `just container=docker
<recipe>`.

> [!TIP]
> On macOS, a `libkrun` Podman machine additionally needs `krunkit`
> (`brew tap slp/krun && brew install krunkit`); `just doctor` will say so if the
> machine won't start.

## Creating a plugin

### 1. Scaffold from the example

```bash
just new-plugin acme-tools
```

This copies `example-plugin/`, renames the bundled server package and Python module,
and rewrites every identifier. You get a complete, working plugin: manifest, two
example skills, and a containerized FastMCP server with tests.

Prefer a different server name, or a skills-only plugin with no server at all:

```bash
just new-plugin acme-tools --server-name acme-api
just new-plugin acme-tools --no-server
```

### 2. Fill in the TODOs

> [!TIP]
> The scaffold deliberately leaves markers that the test suite **fails on** until you
> replace them — that is the guardrail, not a bug.

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

### 3. Write skills

A skill is a directory under `skills/` containing `SKILL.md` with YAML frontmatter.
`name` must match the directory name; `description` should say both *what* it does and
*when* to use it, since that is what an agent matches against.

```markdown
---
name: acme-lookup
description: Looks up an Acme part number and returns its specifications. Use when the user mentions an Acme part, SKU, or catalog number.
---

# Acme lookup

Run the bundled script and summarize the result:

    uv run --script scripts/lookup.py <part-number>
```

On macOS/Linux the shebang also allows `./scripts/lookup.py`. Prefer showing the
`uv run --script` form in `SKILL.md`, since Windows does not honor shebangs.

Bundled scripts are self-contained [PEP 723](https://peps.python.org/pep-0723/) files
— dependencies are declared inline and resolved by `uv`, so no install step is needed
and the skill directory stays copyable:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
```

Mark them executable — the test suite enforces this via git's index mode, so it works
the same on every platform:

```bash
chmod +x scripts/lookup.py                      # macOS / Linux
git update-index --chmod=+x scripts/lookup.py   # any platform, incl. Windows
```

### 4. Write MCP servers

Servers use [FastMCP](https://gofastmcp.com/) — the canonical reference for the
framework — and implement the
[Model Context Protocol](https://modelcontextprotocol.io/specification/), the
canonical reference for the protocol itself.

Define tools in `server.py` and keep transport concerns in `__main__.py`, so the `mcp`
object stays importable for fast in-memory tests:

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

#### How servers and `mcp.json` relate

The server *source* lives in the plugin; the *running service* does not. A client
never launches these servers — it only reads the `url` from `mcp.json` and connects.
Deploy the container yourself, then point `mcp.json` at it:

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

> [!WARNING]
> No placeholder expansion in `url`, and no portable auth — see
> [Deploying a plugin's server](#deploying-a-plugins-server) for both constraints.
> `headers` are visible package data; the test suite rejects credential-looking header
> names, but never rely on that as your only safeguard.

### 5. Test

```bash
just test          # everything
just test-fast     # skip subprocess/network round trips
```

Server tests use FastMCP's in-memory transport — full protocol, no network, no ports:

```python
from fastmcp import Client
from acme_server import mcp


async def test_lookup():
    async with Client(mcp) as client:
        result = await client.call_tool("lookup", {"part_number": "A-1"})
    assert result.data == {...}
```

Repo-level tests **auto-discover** every `*/plugin.json`, so your plugin is validated
against the canonical JSON Schemas, the Agent Skills spec, and this repo's conventions
with **no test edits required**.

For verbose expected values, use
[`inline-snapshot`](https://15r10nk.github.io/inline-snapshot/): write `snapshot()`,
run `just snapshot-fix`, then **review the diff** — a passing fix means code and test
agree, not that the value is correct.

### 6. Submit

```bash
just check    # must pass
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the pull request checklist and process.

## Toolchain

All Python tooling runs through [`uv`](https://docs.astral.sh/uv/) — no `venv`, `pip`,
`pyenv`, or `poetry`. The repo is a **uv workspace**: each server is its own package,
resolved into one root `uv.lock` so container builds are reproducible.

| Tool | Purpose | Platforms | Recipe |
| --- | --- | --- | --- |
| [`uv`](https://docs.astral.sh/uv/) | Packaging + workspace (Rust) | all | `just sync` |
| [`just`](https://just.systems/) | Task runner (Rust) | all (PyPI: `rust-just`) | `just --list` |
| [`ruff`](https://docs.astral.sh/ruff/) | Lint + format (Rust) | all | `just lint` / `just fmt` |
| [`ty`](https://docs.astral.sh/ty/) | Type check (Rust) | all | `just typecheck` |
| [`taplo`](https://taplo.tamasfe.dev/) | TOML format (Rust) | all | `just fmt` |
| [`typos`](https://github.com/crate-ci/typos) | Spell check (Rust) | all | `just spell` |
| [`pytest`](https://docs.pytest.org/) | Tests | all | `just test` |
| [`trivy`](https://trivy.dev/) | Vulns, secrets, misconfig (Go) | all, *optional* | `just security` |
| [`podman`](https://podman.io/) | Container build + run (Go) | all, *optional* | `just image-build` |
| [`pre-commit`](https://pre-commit.com/) | Git hooks | all | `just install-hooks` |

Every tool above except `podman` and `trivy` installs from PyPI through `uv`, which is
why `uv` is the single prerequisite.

Run `just` to list every recipe, or `just doctor` to check your setup. Conventions and
rationale live in [`AGENTS.md`](./AGENTS.md).

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

### Project docs

| Document | Purpose |
| --- | --- |
| [`AGENTS.md`](./AGENTS.md) | Conventions and rationale — read before contributing |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Process, ground rules, PR checklist |
| [`SECURITY.md`](./SECURITY.md) | Reporting vulnerabilities; credential policy |
