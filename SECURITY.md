# Security Policy

## Reporting a vulnerability

Please report security issues privately via
[GitHub's private vulnerability reporting](https://github.com/markbsigler/plugins/security/advisories/new)
rather than opening a public issue.

Include the affected plugin or script, what an attacker could achieve, and
steps to reproduce.

## Scope

This repository contains plugin *packages*: manifests, skill scripts, and MCP
server source. Relevant concerns include:

- A skill script or MCP server tool that executes untrusted input unsafely.
- A `mcp.json` pointing at an endpoint the plugin author does not control.
- Committed credentials (see below).
- A container image that runs as root or ships unnecessary attack surface.

Out of scope: vulnerabilities in `uv`, `just`, `podman`, `trivy`, FastMCP, or
other upstream tools — report those to their maintainers.

## Credentials

Agent Plugins v1 defines **no portable credential or OAuth field**;
authentication is client-managed. `headers` and `env` values in `mcp.json` are
visible package data, so credentials must never be placed there. The test
suite rejects credential-looking header names, and `trivy` scans for committed
secrets as a backstop — neither is a substitute for not committing them.

If you believe a credential has been committed, report it privately using the
link above and do not open a public issue.

## Automated checks

```bash
just security      # trivy: vulnerabilities, secrets, and misconfigurations
just check         # includes the above plus the full test suite
```

`trivy` is optional tooling; `just security` skips with a message when it is
not installed, so ensure it is present before relying on the result.
