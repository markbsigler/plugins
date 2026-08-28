# Contributing

Thanks for contributing. The full walkthrough lives in the
[README](./README.md#contributing-a-new-plugin); this page covers the process
around it.

## Before you start

Read [`AGENTS.md`](./AGENTS.md). It is the source of truth for this repo's
conventions and explains *why* things are the way they are — the `uv`-only
toolchain, the split between PEP 723 skill scripts and packaged servers, and
the portability rules that keep the repo working on Windows.

## Setup

The only prerequisite is [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install rust-just
just install        # installs remaining tools and syncs the workspace
just check          # must pass before you open a PR
```

`just doctor` diagnoses a broken environment without changing anything.

## Ground rules

**Use the scaffolding.** Run `just new-plugin <name>` rather than hand-building
a plugin directory. It applies the naming rules and wires up the workspace
correctly.

**`just check` must pass.** There is no CI on this repository, so the test
suite and pre-commit hooks are the only enforcement. Please run
`just install-hooks` once so checks run automatically on commit.

**Don't put logic in the `justfile`.** Recipes must stay shell-agnostic so they
work on Windows. Anything needing a loop, conditional, or cleanup handler goes
in `scripts/*.py`. `tests/test_portability.py` enforces this.

**Never commit credentials.** `mcp.json` `headers` and `env` are visible
package data, not a secrets mechanism. Agent Plugins v1 has no portable
credential field; authentication is client-managed.

## Adding a plugin

1. `just new-plugin acme-tools`
2. Replace the `TODO` values in `plugin.json`, set the real server URL in
   `mcp.json`, and implement your skills and tools.
3. `just sync && just check`

New plugins are validated automatically — the test suite discovers every
`*/plugin.json` and parametrizes across it, so you should not need to edit
`tests/` to get coverage. If you add a *new kind* of check, add it as a
discovery-driven test rather than one hardcoded to your plugin.

## Pull requests

Keep PRs focused on one plugin or one concern. In the description, say what
the plugin does and, if it ships an MCP server, where it is deployed.

Checklist:

- [ ] `just check` passes
- [ ] Directory name matches `plugin.json` `name`
- [ ] No `TODO` or template placeholders left in manifests
- [ ] Skill `description` fields explain both *what* and *when*
- [ ] Every MCP tool has a docstring (it becomes the model-facing description)
- [ ] `uv.lock` committed if dependencies changed

## Reporting bugs

Open an issue with the output of `just doctor`, your OS, and the exact command
that failed. For security issues, see [`SECURITY.md`](./SECURITY.md) instead.
