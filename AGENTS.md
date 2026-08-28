# AGENTS.md

Instructions for coding agents (and humans) working in this repository.

This repo is a collection of **Agent Plugins**: portable packages of Agent
Skills and MCP servers built to the
[Agent Plugins Specification v1.0.0](https://agent-plugins.org/specification).
Every plugin component that runs code (skill scripts, MCP servers) is written
in Python. Read this whole file before adding or modifying a plugin.

The specification text at https://agent-plugins.org/specification is
authoritative. This document summarizes it for day-to-day work; if anything
here conflicts with the published spec, the spec wins.

## 1. Repository layout

- Every top-level directory that contains a `plugin.json` **is** a plugin and
  must be usable on its own if copied elsewhere. Do not make a plugin
  directory depend on files outside itself (no relative imports of code in
  sibling plugins, no reliance on the repo root `pyproject.toml`).
- `README.md`, `AGENTS.md`, root `pyproject.toml`, `justfile`,
  `.pre-commit-config.yaml`, `schemas/`, and `tests/` are repo-level
  developer tooling, not plugin content. Never place them inside a plugin
  directory, and never make plugin behavior depend on them.
- [`my-plugin/`](./my-plugin) is the canonical scaffold. Copy it when
  starting a new plugin rather than building the layout from scratch.
- [`schemas/1.0.0/`](./schemas/1.0.0) vendors the canonical
  `plugin.schema.json`/`mcp.schema.json` from agent-plugins.org, used by
  `tests/test_schema_validation.py`. Re-fetch them if/when this repo moves
  to a newer Agent Plugins spec version.

## 2. The Agent Plugins package format (summary)

### 2.1 Plugin package model

- A plugin is a single directory. It **must** contain `plugin.json` at its
  root.
- Every file path a plugin declares (e.g. an MCP `command` or `cwd`) that the
  spec defines as plugin-relative **must** start with `./` and resolve to a
  location inside the plugin root, even through symlinks. Never write a path
  that can escape the plugin directory (e.g. `../`, absolute paths).
- Command arguments, environment variable values, and HTTP headers are opaque
  strings — they are not path-checked, but see §2.4 on placeholders and §2.3
  on secrets.

### 2.2 Manifest (`plugin.json`)

- Must be a JSON object with a **closed** set of top-level fields:
  `$schema` (required), `name` (required), `version`, `description`,
  `author`, `homepage`, `repository`, `license`, `keywords`, `extensions`.
  Do not add any other top-level field — put client-specific data under
  `extensions`, keyed by a reverse-domain namespace you own
  (e.g. `com.example.client`).
- `$schema` **must** be exactly
  `"https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"`.
- `name` constraints: 1-64 characters, lowercase ASCII letters/digits/`-`/`.`
  only, must start and end with an alphanumeric character, and must not
  contain `--` or `..`. Valid: `my-plugin`, `acme.tools`. Invalid:
  `My-Plugin`, `-start`, `has--double`.
- Prefer keeping the plugin's directory name identical to its manifest
  `name`.
- `version` should follow Semantic Versioning; `license` should be an SPDX
  identifier; these are recommendations, not hard requirements enforced by
  the schema.

### 2.3 Component types (fixed locations only)

Agent Plugins v1 defines exactly two portable component types, discovered
only from fixed locations. `plugin.json` never contains inline component
configuration.

| Component type | Fixed location | Discovery rule |
| --- | --- | --- |
| Skills | `skills/` | Each **immediate** child directory containing a regular file named exactly `SKILL.md` is one skill. Not recursive. |
| MCP servers | `mcp.json` | A JSON object with only `$schema` and `mcpServers`. |

- Skills follow the [Agent Skills specification](https://agentskills.io/specification)
  exactly: `SKILL.md` needs YAML frontmatter with required `name` (matches
  the parent directory name, lowercase, hyphenated) and `description`
  (specific enough that an agent knows when to invoke it), plus optional
  `license`, `compatibility`, `metadata`, `allowed-tools`.
- `mcp.json` server entries are one of three transports:
  - `stdio`: requires `type`, `command`; optional `args`, `env`, `cwd`.
    `command` is a single token - a bare executable name or a
    plugin-relative path starting with `./`. It is **not** placeholder
    expanded. If you bundle an interpreter script, use a plugin-relative
    `command` (don't rely on `PATH`).
  - `streamable-http` / `sse` (`sse` is deprecated): requires `type`, `url`;
    optional `headers`. `url` must be absolute HTTP(S), no userinfo or
    fragment, and non-loopback endpoints must use HTTPS.
  - An invalid `mcp.json` disables MCP for the whole plugin; an invalid
    individual server entry disables only that entry. Keep servers
    independent so one bad config doesn't take down the others.
- A missing `skills/` or missing `mcp.json` is fine - it's just an absent
  component type, not an error.

### 2.4 Placeholders and plugin variables

- Clients provide `PLUGIN_ROOT` (absolute plugin root) and `PLUGIN_DATA` (a
  writable, update-persistent data directory) as environment variables to
  stdio subprocesses.
- `${PLUGIN_ROOT}` and `${PLUGIN_DATA}` are expanded (textually, single-pass)
  in `args`, `env` values, and `cwd` - **never** in `command`, header names,
  header values, or remote `url`.
- Never hardcode absolute paths in `mcp.json`; use `${PLUGIN_ROOT}` /
  `${PLUGIN_DATA}` or a plugin-relative path instead.

### 2.5 Secrets

- `headers` in `mcp.json` and any committed `env` values are **visible
  package data**, not a secrets mechanism. Never put credentials, tokens, or
  API keys there. Agent Plugins v1 has no portable credential/OAuth field -
  authentication is client-managed, so don't try to invent one.

### 2.6 Client extensions

- Only add data under `extensions.<namespace>` or an `<namespace>/` top-level
  directory for a namespace you own and document (reverse-domain style,
  e.g. `com.example.client`). Don't invent hooks/agents/commands/etc. at the
  portable top level - those belong in a namespaced extension, if anywhere.

## 3. Python practices for plugin components

Everything a plugin executes (skill `scripts/`, MCP servers) is Python. Since
each plugin directory must stay copyable and self-contained, prefer patterns
that avoid a separate install step over a repo-wide virtualenv.

### 3.1 Use `uv` exclusively

- This repo standardizes on [`uv`](https://docs.astral.sh/uv/) for
  **everything** Python: running scripts, managing the repo dev tooling, and
  resolving dependencies. Do not introduce `venv`, `pip`, `pipx`, `pyenv`,
  `poetry`, or a manually-managed virtualenv/requirements.txt — if a task
  seems to need one of those, there's a `uv` equivalent (`uv run`, `uv sync`,
  `uv add`, `uv run --script`, `uv python install`). Ask before adding any
  other Python packaging/dependency tool.
- Never commit a `requirements.txt`. Dependencies live either in a PEP 723
  script's inline metadata (§3.2) or in a `pyproject.toml` managed by `uv`
  (`uv add`/`uv remove`), with the resulting `uv.lock` committed alongside it.

### 3.2 Prefer PEP 723 self-contained scripts

- For skill scripts and MCP servers, use a single `.py` file with a
  [PEP 723](https://peps.python.org/pep-0723/) inline metadata block
  declaring `requires-python` and `dependencies`, executed via
  `#!/usr/bin/env -S uv run --script` and `chmod +x`. This lets `command` in
  `mcp.json` point straight at the script (`./servers/echo_server.py`) with
  no environment to provision ahead of time - `uv` resolves and caches
  dependencies on first run.
- Only reach for a full package (`pyproject.toml`, `src/` layout, installed
  console-script entry point) inside a plugin directory when a single-file
  script genuinely doesn't scale (multiple modules, shared internal code
  across scripts). Keep it inside that plugin's own directory - never make
  one plugin import code from another.
- Pin a minimum Python version with `requires-python` in every script's
  inline metadata (this repo targets `>=3.11`).

### 3.3 Data validation and processing: Pydantic v2 and polars

- Use [Pydantic v2](https://docs.pydantic.dev/latest/) (`pydantic.BaseModel`)
  to validate and shape structured input/output at a component's boundaries
  — a script's stdout, an MCP tool's return value, an HTTP request/response
  body — instead of hand-rolled dicts or manual validation. See
  `skills/table-stats/scripts/table_stats.py` (script output) and
  `servers/remote_server.py`'s `/echo` endpoint (FastAPI request/response
  models) for examples.
  - Use v2 APIs only: `model_dump()`/`model_dump_json()`,
    `model_validate()`/`model_validate_json()`, `Field(...)`. Don't use the
    deprecated v1 methods (`.dict()`, `.json()`, `.parse_obj()`).
  - Prefer `Field` constraints (`min_length`, `ge`/`le`, etc.) over
    hand-written validation for simple invariants; reach for
    `@field_validator`/`@model_validator` for anything more involved.
  - FastAPI (§3.6) already uses Pydantic v2 natively for request/response
    validation — declare a `BaseModel` parameter/return type and let FastAPI
    call it, rather than parsing `request.json()` by hand.
- Use [polars](https://pola.rs/) for any tabular/dataframe work — don't
  introduce `pandas` without asking first. Prefer the lazy API
  (`pl.scan_csv(...).collect()`, `LazyFrame` method chains) over the eager
  `pl.read_csv`/`DataFrame` API once a dataset might not comfortably fit in
  memory, or when several filter/aggregate steps can be pushed down and
  optimized together.
- Both are opt-in per component: declare them in that script's own PEP 723
  `dependencies` (§3.2), not in the repo root `pyproject.toml`.

### 3.4 Code quality

- Add type hints on all function signatures; avoid bare `Any` when a
  concrete type is known.
- Use `pathlib.Path` instead of raw string path manipulation.
- Use `argparse` (stdlib) for script CLIs unless a dependency is already
  required for another reason.
- Prefer `logging` over `print` for anything other than a script's actual
  stdout result (MCP servers must never write logs to stdout - that stream
  is the protocol channel; log to stderr or a file if needed).
- Never use `shell=True` in `subprocess` calls; pass argument lists.
- Handle expected failure modes explicitly (missing files, bad input) and
  fail with clear, non-zero exit codes rather than uncaught tracebacks.
- Write docstrings (module and public function level) - PEP 257 style -
  especially for MCP `@mcp.tool()` functions, since their docstring often
  becomes the tool description shown to a model.
- Keep scripts deterministic and side-effect free unless a skill's
  `description` says otherwise.

### 3.5 Formatting, linting, typing, testing

Repo-level dev tooling lives in the root [`pyproject.toml`](./pyproject.toml)
and runs via `uv` without needing a manual `pip install`:

```bash
uv sync                 # provision the dev tool virtualenv once
uv run ruff check .     # lint
uv run ruff format .    # format
uv run ty check .       # type-check repo-level code
uv run pytest           # run tests under tests/
```

Equivalent [`just`](https://just.systems/) recipes exist for all of these
(§3.9) — prefer `just <recipe>`/`just check` day to day so the exact command
stays in one place (the `justfile`) instead of drifting between this
document and habit.

- `ruff` is the linter and formatter (replaces flake8/black/isort).
- [`ty`](https://docs.astral.sh/ty/) (Astral's type checker) checks
  repo-level code — use `ty`, not `mypy` or `pyright`, unless asked
  otherwise. Individual PEP 723 scripts under `skills/*/scripts/` and
  `*/servers/` are excluded from this repo-wide `ty` run (see
  `[tool.ty.src].exclude` in `pyproject.toml`) because their dependencies
  live in `uv`'s per-script cache, not this repo's dev virtualenv -
  type-check those with `uv run --with ty --with <script's deps> ty check
  path/to/script.py` instead when you touch one.
- Still run `ruff check`/`ruff format` against every script - those don't
  need the script's own dependencies installed.
- Add or update tests in [`tests/`](./tests) for structural/manifest changes
  (see `tests/test_my_plugin_manifest.py`), and add focused unit or
  subprocess-driven integration tests next to any nontrivial script or
  server logic you add (see `tests/test_my_plugin_servers.py`, which spawns
  `echo_server.py` and `remote_server.py` via `uv run --script`/`--with`
  rather than importing their dependencies into the shared dev
  environment). Mark tests that spawn a full server `@pytest.mark.slow`.
- **Validate `plugin.json`/`mcp.json` against the real, canonical schemas**
  (§1's `schemas/1.0.0/`) via [`jsonschema`](https://python-jsonschema.readthedocs.io/),
  not only the hand-written structural checks in
  `tests/test_my_plugin_manifest.py` — see
  `tests/test_schema_validation.py`. When adding a new plugin, either extend
  that test to cover it or add an equivalent schema-validation test next to
  the new plugin's own tests. The specification text remains authoritative
  over the schema (§2.2) if the two ever disagree.
- Use [`inline-snapshot`](https://15r10nk.github.io/inline-snapshot/)
  (`from inline_snapshot import snapshot`) for expected values that are
  verbose or annoying to hand-write (JSON blobs, computed structures,
  captured stdout) instead of writing them out by hand — see
  `tests/test_my_plugin_scripts.py` and the `/echo` assertions in
  `tests/test_my_plugin_servers.py`. Prefer a plain `assert` for simple
  scalar/boolean checks; reserve snapshots for larger structured values.
  - Write `snapshot()` (or a snapshot with a placeholder value) and run
    `uv run pytest --inline-snapshot=create` to fill it in, or
    `--inline-snapshot=fix` (or `just snapshot-fix`) to correct an existing
    snapshot after an intentional behavior change.
  - **Always read the diff before committing a snapshot change** — a
    passing `fix`/`create` run means the code and test now agree, not that
    the new value is correct. If a snapshot changed because of a bug fix,
    great; if it changed because of a regression, fix the regression
    instead of accepting the new snapshot.
  - `[tool.inline-snapshot]` in `pyproject.toml` sets `format-command` so
    fixed snapshots come out `ruff format`-clean automatically.

### 3.6 `fastapi` for HTTP-based components

Use [FastAPI](https://fastapi.tiangolo.com/) (with `uvicorn` to serve it) for
any plugin component that speaks HTTP:

- A `streamable-http` or `sse` MCP server (see §2.3): mount the MCP SDK's
  `MCPServer.streamable_http_app()` / `.sse_app()` Starlette app inside a
  FastAPI app so you can add health checks, auth, or logging alongside the
  MCP protocol. See `my-plugin/servers/remote_server.py` for a working
  example, including the lifespan wiring `session_manager.run()` needs.
- Remember the portability distinction: a conformant client only ever
  launches a plugin's `stdio` servers as a subprocess. A `streamable-http`/
  `sse` server is deployed and run independently of the client — `mcp.json`
  only stores the `url` it listens on. Don't expect `command`/`args`/`cwd`
  semantics to apply to it.
- Declare `fastapi` and `uvicorn` in that script's own PEP 723 metadata
  (§3.2), not in the repo root `pyproject.toml`.
- Keep FastAPI route handlers thin; put logic in separately testable
  functions where practical.

### 3.7 Security scanning with `trivy`

This repo uses [`trivy`](https://trivy.dev/) as its security scanner —
don't substitute `pip-audit`, `safety`, `bandit`, or similar tools without
asking first.

```bash
trivy fs --config trivy.yaml .
```

- Config lives at [`trivy.yaml`](./trivy.yaml) and enables the `vuln`,
  `secret`, and `misconfig` scanners with `CRITICAL`/`HIGH`/`MEDIUM`
  severities and a non-zero exit code on findings.
- Run it whenever you add or change a dependency (`uv.lock`, or a PEP 723
  script's inline `dependencies`), and before committing any new plugin.
- If a finding is a real issue, fix it (bump the dependency, remove the
  secret, correct the misconfiguration) rather than suppressing it.
- If a finding is a reviewed false positive or accepted risk, add it to
  [`.trivyignore`](./.trivyignore) with a comment explaining why — never
  suppress silently.
- Never commit real secrets, tokens, or credentials anywhere in this repo,
  including in `mcp.json` `env`/`headers` (see §2.5) — `trivy`'s secret
  scanner is a backstop, not a substitute for not doing that.

### 3.8 Task runner: `just`

The [`justfile`](./justfile) at the repo root is the canonical list of dev
commands — prefer `just <recipe>` over remembering/retyping the underlying
`uv run ...`/`trivy ...` invocations, and update the `justfile` (not just
this document) if a command changes.

```bash
just                # list all recipes
just check          # ruff + ty + pytest + trivy (what "before committing" means)
just lint-fix        # ruff check --fix
just test-fast       # pytest -m "not slow"
just snapshot-fix     # uv run pytest --inline-snapshot=fix
just pre-commit-all   # run every pre-commit hook against all files
```

`just` itself is a small Rust binary, not a Python package, so install it
however you prefer (`brew install just`, etc.) rather than through `uv`.

### 3.9 Pre-commit hooks

[`.pre-commit-config.yaml`](./.pre-commit-config.yaml) wires the same
checks into `git commit` via the [pre-commit](https://pre-commit.com/)
framework, run with `uv`'s ad hoc tool runner rather than `pip install
pre-commit`:

```bash
uvx pre-commit install          # one-time: install the git hook
uvx pre-commit run --all-files  # run every hook against the whole repo
```

- A handful of generic file-hygiene hooks
  (`pre-commit/pre-commit-hooks`: trailing whitespace, EOF newline, merge
  conflict markers, large files, JSON syntax) run in pre-commit's own
  isolated hook environments — that's how the pre-commit framework always
  manages hooks from third-party repos, and it doesn't conflict with using
  `uv` for this repo's own Python code.
- The `ruff`/`ty`/`pytest`/`trivy` hooks are `local`/`language: system`
  hooks that call straight through to this repo's own tooling (`uv run
  ruff check --fix`, `uv run ty check .`, `uv run pytest -m "not slow"`,
  `trivy fs --config trivy.yaml .`), so they stay identical to the
  `justfile` recipes instead of a second, separately pinned copy of the
  same tools.
- The `pytest` hook only runs the fast suite (`-m "not slow"`) to keep
  commits quick; run `just test` (the full suite, including the
  subprocess-spawned server integration tests) before pushing or opening a
  PR.
- If you add a new repo-level tool, add both a `justfile` recipe and a
  pre-commit hook for it so the two don't drift apart.

### 3.10 Before committing

Run `just check` (§3.8), which covers:

1. `ruff check` and `ruff format --check`
2. `ty check`
3. `pytest` (the full suite)
4. `trivy fs --config trivy.yaml .`

Then, manually:

5. Exercise any new/changed script or MCP server directly (see
   `my-plugin/README.md` for examples).
6. Re-read `plugin.json` / `mcp.json` diffs against §2 above - a schema
   violation there is fatal for the whole plugin; `just test` also runs
   `tests/test_schema_validation.py` against the canonical schemas.

If you have the git hook installed (§3.9), `uvx pre-commit run --all-files`
(or `just pre-commit-all`) exercises the same tools plus the file-hygiene
hooks in one pass.

## 4. Checklist for a new plugin

- [ ] Copied `my-plugin/` (or built fresh) with a valid, unique directory
      name matching the manifest `name`.
- [ ] `plugin.json` has `$schema`, `name`, and only otherwise-allowed fields.
- [ ] Each skill lives at `skills/<skill-name>/SKILL.md` with valid
      frontmatter; scripts are PEP 723 self-contained and executable.
- [ ] `mcp.json` (if present) has only `$schema`/`mcpServers`, uses
      plugin-relative or bare `command`, and uses `${PLUGIN_ROOT}`/
      `${PLUGIN_DATA}` for any path-like `args`/`env`/`cwd` values.
- [ ] No secrets in `mcp.json` headers/env.
- [ ] Added or extended a schema-validation test (`tests/test_schema_validation.py`
      or an equivalent alongside the new plugin) so `plugin.json`/`mcp.json`
      are checked against the canonical schemas, not only hand-written checks.
- [ ] `trivy fs --config trivy.yaml .` run clean (or findings triaged in
      `.trivyignore` with a comment).
- [ ] Any client-specific behavior lives under a namespaced `extensions`
      entry or extension directory, not at the portable top level.
- [ ] `just check` (ruff + ty + pytest + trivy) passes from the repo root.
