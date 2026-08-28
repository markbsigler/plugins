# AGENTS.md

Instructions for coding agents (and humans) working in this repository.

This repo is a collection of **Agent Plugins**: portable packages of Agent
Skills and MCP servers built to the
[Agent Plugins Specification v1.0.0](https://agent-plugins.org/specification).
MCP servers are built with [FastMCP](https://gofastmcp.com/) and deployed as
containers over Streamable HTTP.

Read this file before adding or modifying a plugin. For the contributor
walkthrough, see [`README.md`](./README.md).

The specification text at https://agent-plugins.org/specification is
authoritative; this document summarizes it and adds repo conventions. If the
two conflict, the spec wins.

## 1. Repository layout

- Any top-level directory containing `plugin.json` **is** a plugin. Discovery
  and validation are driven by that glob, so a new plugin directory is
  automatically covered by the test suite with no test edits.
- [`my-plugin/`](./my-plugin) is the canonical example. **Never hand-build a
  new plugin** — run `just new-plugin <name>`, which copies it and rewrites
  every identifier.
- Repo-level tooling — `README.md`, `AGENTS.md`, `pyproject.toml`, `justfile`,
  `.pre-commit-config.yaml`, `schemas/`, `scripts/`, `tests/` — is not plugin
  content. Never place it inside a plugin, and never make plugin behavior
  depend on it.
- [`schemas/1.0.0/`](./schemas/1.0.0) vendors the canonical Agent Plugins JSON
  Schemas used by the tests. Refresh with `just update-schemas`.

### 1.1 The repo is a `uv` workspace

Each MCP server under `*/servers/*` is its own Python package and a workspace
member (`[tool.uv.workspace] members = ["*/servers/*"]`). One root `uv.lock`
pins every server together, so container builds are reproducible and match
local development.

Always sync with **`just sync`** (`uv sync --all-packages`), which installs
every workspace member. A plain `uv sync` will not install newly added
servers, and their tests will fail to import.

## 2. The Agent Plugins package format (summary)

### 2.1 Plugin package model

- A plugin is one directory and **must** contain `plugin.json` at its root.
- Any spec-defined plugin-relative path must start with `./` and resolve
  inside the plugin root, even through symlinks. Never write a path that can
  escape (`../`, absolute paths).
- Command arguments, environment values, and HTTP headers are opaque strings —
  not path-checked. See §2.4 and §2.5.

### 2.2 Manifest (`plugin.json`)

- The schema is **closed**. Only these top-level fields are permitted:
  `$schema` (required), `name` (required), `version`, `description`, `author`,
  `homepage`, `repository`, `license`, `keywords`, `extensions`. Anything else
  belongs under `extensions`, keyed by a reverse-domain namespace you own.
- `$schema` must be exactly
  `"https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"`.
- `name`: 1–64 chars, lowercase ASCII letters/digits/`-`/`.`, must start and
  end alphanumeric, no `--` or `..`. Valid: `my-plugin`, `acme.tools`.
  Invalid: `My-Plugin`, `-start`, `has--double`.
- Keep the directory name identical to `name` (enforced by tests).

### 2.3 Component types (fixed locations only)

Agent Plugins v1 defines exactly two portable component types, discovered only
from fixed locations. `plugin.json` never contains inline component config.

| Component | Location | Discovery rule |
| --- | --- | --- |
| Skills | `skills/` | Each **immediate** child directory containing a regular `SKILL.md`. Not recursive. |
| MCP servers | `mcp.json` | JSON object with only `$schema` and `mcpServers`. |

A missing `skills/` or `mcp.json` is fine — just an absent component type.

**`servers/` is not a portable component.** It holds build-time source for the
containers you deploy. Conformant clients read only `plugin.json`, `skills/`,
and `mcp.json`, so they ignore it. This is intentional: consolidating server
source with the plugin that declares it is worth carrying build material in
the package. Do not "fix" this by moving servers out.

### 2.4 Transports and placeholders

- This repo deploys **`streamable-http`** servers. `stdio` entries are
  supported by the spec but are not the pattern here.
- Remote entries require `type` and `url`; `url` must be absolute HTTP(S),
  with no userinfo or fragment, and non-loopback endpoints must use HTTPS.
- `${PLUGIN_ROOT}` / `${PLUGIN_DATA}` expand **only** in a stdio entry's
  `args`, `env`, and `cwd` — never in `command`, `url`, or headers.
- **Consequence:** one manifest cannot parameterize dev/staging/prod URLs.
  Ship the production URL, or maintain per-environment plugin variants.

### 2.5 Secrets

`headers` and committed `env` values are **visible package data**, not a
secrets mechanism. Never put credentials, tokens, or API keys there — tests
reject credential-looking header names. Agent Plugins v1 defines no portable
OAuth or credential field; authentication is client-managed. Do not invent one.

### 2.6 Client extensions

Only add data under `extensions.<namespace>` or a top-level `<namespace>/`
directory for a reverse-domain namespace you own and document. Don't invent
hooks/agents/commands at the portable top level.

## 3. Python conventions

### 3.1 Use `uv` exclusively

- `uv` for everything: running, dependency management, resolution. Do **not**
  introduce `venv`, `pip`, `pipx`, `pyenv`, or `poetry`. There is a `uv`
  equivalent for each (`uv run`, `uv sync`, `uv add`, `uv run --script`,
  `uv python install`). Ask before adding any other packaging tool.
- Never commit `requirements.txt`. Dependencies belong in a PEP 723 inline
  block (skills) or a package `pyproject.toml` managed by `uv` (servers),
  with the root `uv.lock` committed.
- `.python-version` pins the interpreter; keep it aligned with the
  `Dockerfile` base image.

### 3.2 Two packaging patterns — pick the right one

This distinction matters; applying the wrong one causes real problems.

**Skill scripts → PEP 723 single files.** Inline `# /// script` metadata,
`#!/usr/bin/env -S uv run --script` shebang, `chmod +x`. Dependencies resolve
on first run, so the skill directory stays self-contained and copyable.

**MCP servers → full packages.** `pyproject.toml`, `src/` layout, workspace
member, locked via root `uv.lock`. PEP 723 is *wrong* here: containers need
pinned, reproducible resolution and a lockfile.

Never make one plugin import code from another.

### 3.3 FastMCP servers

Use [FastMCP](https://gofastmcp.com/) — not the lower-level `mcp` SDK — for
every MCP server.

**Structure matters.** Keep `server.py` free of transport concerns:

```python
# src/<pkg>/server.py  — tools only
from fastmcp import FastMCP

mcp = FastMCP(name="my-server", instructions="...")


@mcp.tool
def do_thing(arg: str) -> dict[str, str]:
    """This docstring becomes the tool description shown to models."""
```

```python
# src/<pkg>/__main__.py  — hosting only
mcp.run(transport="http", host=..., port=...)
```

That split is what makes in-memory testing (§3.5) possible. Also:

- `@mcp.tool` takes no parentheses in FastMCP 3.x.
- **Write real docstrings on every tool** — they become the model-facing
  description. A tool without one is nearly unusable; tests enforce this.
- Type-hint tool signatures; FastMCP derives the JSON schema from them.
- Read host/port/allowlists from the environment so one image runs anywhere.
- Set `allowed_hosts`/`allowed_origins` in production (DNS-rebinding
  protection).
- Never log to stdout in a stdio server; for HTTP servers prefer `logging`.
- Each server carries a `fastmcp.json` (canonical FastMCP config) and a
  multi-stage, non-root `Dockerfile`. `just inspect-server` dumps the tool
  surface.

### 3.4 Data validation and processing

- **Pydantic v2** for structured input/output at boundaries — script stdout,
  tool returns, HTTP bodies. Use v2 APIs only (`model_dump()`,
  `model_validate()`, `Field`), never v1 (`.dict()`, `.parse_obj()`). Prefer
  `Field` constraints over hand-rolled validation.
- **polars** for tabular work — not `pandas` without asking. Prefer the lazy
  API (`pl.scan_csv(...).collect()`) for anything that may not fit in memory.
- Declare these per component (PEP 723 block or the server's `pyproject.toml`),
  never in the repo root.

### 3.5 Testing

```bash
just test          # everything
just test-fast     # skip subprocess/network round trips
```

- **Server tests use FastMCP's in-memory transport**: `Client(mcp)` speaks the
  full protocol with no network, subprocess, or ports. This is the default;
  reach for a real HTTP round trip only when testing transport itself, and
  mark it `@pytest.mark.slow`.
- `asyncio_mode = "auto"` — async tests need no decorator.
- **Repo-level tests auto-discover plugins.** Any test taking `plugin_dir`,
  `skill_dir`, or `server_dir` is parametrized across everything found. Add
  new *checks*, never new hardcoded plugin names.
- Tests use `--import-mode=importlib`, so every server can reuse the
  `tests/test_server.py` basename without collisions.
- Use [`inline-snapshot`](https://15r10nk.github.io/inline-snapshot/) for
  verbose expected values: write `snapshot()`, run `just snapshot-fix`, then
  **read the diff**. A passing fix means code and test agree — not that the
  new value is correct.

### 3.6 Code quality

- Type hints on all signatures; avoid bare `Any` when a concrete type exists.
- `pathlib.Path` over string path manipulation (enforced by ruff `PTH`).
- Google-style docstrings (`D` ruleset).
- Never `shell=True`; pass argument lists.
- Handle expected failures explicitly with clear non-zero exits, not
  tracebacks.
- Suppress a lint only with a **targeted, explained** `# noqa: RULE`. `RUF100`
  fails the build on stale suppressions.

### 3.7 Tooling

Everything runs through `just` — prefer recipes over retyping commands, and
update the `justfile` (not just this doc) when a command changes.

| Tool | Purpose |
| --- | --- |
| `ruff` | Lint + format |
| `ty` | Type check (**not** mypy/pyright) |
| `taplo` | TOML formatting |
| `typos` | Spell check |
| `pytest` | Tests |
| `trivy` | Vulnerabilities, secrets, misconfig |

`ty` skips PEP 723 scripts (`[tool.ty.src].exclude`) because their deps live in
`uv`'s per-script cache. Type-check one with
`uv run --with ty --with <deps> ty check <path>`.

For `trivy`: fix real findings rather than suppressing them; if a finding is a
reviewed false positive, add it to [`.trivyignore`](./.trivyignore) **with a
comment**. Never suppress silently.

Pre-commit (`just install-hooks`) runs the same tools as `language: system`
hooks calling this repo's toolchain, so hooks and `justfile` can't drift. If
you add a repo-level tool, add **both** a recipe and a hook.

### 3.8 Before committing

Run **`just check`** (lint, format, types, spelling, tests, security). Then:

1. Exercise any new/changed script or server directly.
2. Re-read `plugin.json` / `mcp.json` diffs against §2 — a schema violation is
   fatal for the whole plugin.
3. If dependencies changed, commit the updated `uv.lock`.

## 4. Checklist for a new plugin

- [ ] Created with `just new-plugin <name>` (not hand-built).
- [ ] Directory name matches manifest `name`.
- [ ] `plugin.json` has only spec-allowed top-level fields; no TODO/template
      values left.
- [ ] Each skill is `skills/<name>/SKILL.md` with frontmatter `name` matching
      its directory and a description saying *what* and *when*.
- [ ] Skill scripts are PEP 723, executable, and have a shebang.
- [ ] `mcp.json` uses `streamable-http` with a real HTTPS URL and no
      credentials in headers.
- [ ] Each server: `fastmcp.json`, `pyproject.toml`, non-root multi-stage
      `Dockerfile`, `__main__.py`, and in-memory tests.
- [ ] Every tool has a docstring.
- [ ] `just sync` run so new workspace members are installed.
- [ ] `just check` passes.
