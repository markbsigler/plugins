#!/usr/bin/env python3
"""Cross-platform toolchain check and setup.

Usage:
    just doctor          # report status only
    just install         # install what is missing, then report

Runs on macOS, Linux, and Windows with no shell dependencies -- it is invoked
through ``uv``, which is this repo's single hard prerequisite.

Tool tiers:

* ``uv``    -- required; bootstraps everything else. Cannot self-install.
* ``just``  -- required; installed from PyPI (``rust-just``) via ``uv tool``,
  which works identically on all three platforms.
* ``podman``-- optional; only needed to build/run container images.
* ``trivy`` -- optional; only needed for security scans.

Python tools (ruff, ty, taplo, typos, pytest) come from the uv workspace via
``uv sync`` and are never installed separately.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

# Package managers we know how to drive, in preference order per platform.
# Each entry maps: manager -> (probe command, install command prefix).
PACKAGE_MANAGERS: dict[str, tuple[str, list[str]]] = {
    "brew": ("brew", ["brew", "install"]),
    "winget": ("winget", ["winget", "install", "-e", "--id"]),
    "scoop": ("scoop", ["scoop", "install"]),
    "choco": ("choco", ["choco", "install", "-y"]),
    "apt": ("apt-get", ["sudo", "apt-get", "install", "-y"]),
    "dnf": ("dnf", ["sudo", "dnf", "install", "-y"]),
    "pacman": ("pacman", ["sudo", "pacman", "-S", "--noconfirm"]),
    "zypper": ("zypper", ["sudo", "zypper", "install", "-y"]),
}

PLATFORM_ORDER: dict[str, list[str]] = {
    "darwin": ["brew"],
    "win32": ["winget", "scoop", "choco"],
    "linux": ["apt", "dnf", "pacman", "zypper", "brew"],
}


@dataclass
class Tool:
    """A tool the repo depends on."""

    name: str
    required: bool
    purpose: str
    # Package name per manager, when it differs from `name`.
    package: dict[str, str] = field(default_factory=dict)
    # Installable with `uv tool install <dist>` (platform-independent).
    uv_package: str | None = None
    version_args: tuple[str, ...] = ("--version",)
    docs: str = ""

    def package_for(self, manager: str) -> str:
        """Return the package name to install for ``manager``."""
        return self.package.get(manager, self.name)


TOOLS: list[Tool] = [
    Tool(
        name="uv",
        required=True,
        purpose="Packaging, workspace, and script running",
        package={"winget": "astral-sh.uv"},
        docs="https://docs.astral.sh/uv/getting-started/installation/",
    ),
    Tool(
        name="just",
        required=True,
        purpose="Task runner",
        uv_package="rust-just",
        package={"winget": "Casey.Just"},
        docs="https://just.systems/man/en/packages.html",
    ),
    Tool(
        name="podman",
        required=False,
        purpose="Build and run container images",
        package={"winget": "RedHat.Podman"},
        docs="https://podman.io/docs/installation",
    ),
    Tool(
        name="trivy",
        required=False,
        purpose="Vulnerability, secret, and misconfiguration scanning",
        package={"winget": "AquaSecurity.Trivy"},
        docs="https://trivy.dev/latest/getting-started/installation/",
    ),
]

WORKSPACE_TOOLS = ("ruff", "ty", "taplo", "typos", "pytest")


def detect_package_manager() -> str | None:
    """Return the preferred available package manager for this platform."""
    for manager in PLATFORM_ORDER.get(sys.platform, PLATFORM_ORDER["linux"]):
        probe, _ = PACKAGE_MANAGERS[manager]
        if shutil.which(probe):
            return manager
    return None


def tool_version(tool: Tool) -> str:
    """Return a one-line version string, or a placeholder if unavailable."""
    exe = shutil.which(tool.name)
    if not exe:
        return "not installed"
    # `trivy --version` loads trivy.yaml and prints INFO noise; `-q` suppresses it.
    args = ["-q", "version"] if tool.name == "trivy" else list(tool.version_args)
    try:
        proc = subprocess.run(  # noqa: S603
            [exe, *args], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "installed (version unknown)"
    output = (proc.stdout or proc.stderr).strip().splitlines()
    return output[0].strip() if output else "installed"


def container_engine_status(engine: str) -> tuple[bool, str]:
    """Return whether ``engine`` is usable, plus a human-readable status."""
    if not shutil.which(engine):
        return False, "not installed"
    try:
        proc = subprocess.run(  # noqa: S603
            [engine, "info"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False, "installed but not responding"
    if proc.returncode == 0:
        return True, "ready"
    return False, "installed but not running"


def workspace_tool_ok(name: str) -> bool:
    """Check a uv-managed workspace tool is importable/runnable."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["uv", "run", "--quiet", name, "--version"],  # noqa: S607
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def discover_server_packages() -> list[tuple[str, str]]:
    """Return (package name, importable module) for every workspace server."""
    servers: list[tuple[str, str]] = []
    for pyproject in REPO_ROOT.glob("*/servers/*/pyproject.toml"):
        src = pyproject.parent / "src"
        if not src.is_dir():
            continue
        for candidate in sorted(src.iterdir()):
            if candidate.is_dir() and (candidate / "__init__.py").is_file():
                servers.append((pyproject.parent.name, candidate.name))
    return sorted(servers)


def server_package_importable(module: str) -> bool:
    """Check a workspace server package is installed in the environment.

    Dev-group tools can be present while workspace members are not (a plain
    ``uv sync`` omits them), so this is checked separately -- otherwise
    doctor reports success on an environment where ``just test`` fails.
    """
    try:
        proc = subprocess.run(  # noqa: S603
            ["uv", "run", "--quiet", "python", "-c", f"import {module}"],  # noqa: S607
            capture_output=True,
            timeout=120,
            check=False,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def sync_workspace() -> bool:
    """Install every workspace member (``uv sync --all-packages``).

    A plain ``uv sync`` installs only the root project's dependency groups
    and actively *uninstalls* workspace members, so servers must be synced
    explicitly or their tests cannot import them.
    """
    print("  sync     uv sync --all-packages")
    try:
        proc = subprocess.run(
            ["uv", "sync", "--all-packages"],  # noqa: S607
            check=False,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"    workspace sync failed: {exc}")
        return False
    return proc.returncode == 0


def install_tool(tool: Tool, manager: str | None) -> bool:
    """Attempt to install ``tool``. Returns True on success."""
    # Prefer uv for anything published to PyPI: identical on every platform,
    # no admin rights, no package-manager differences.
    if tool.uv_package and shutil.which("uv"):
        print(f"    installing {tool.name} via: uv tool install {tool.uv_package}")
        proc = subprocess.run(  # noqa: S603
            ["uv", "tool", "install", tool.uv_package],  # noqa: S607
            check=False,
        )
        if proc.returncode == 0:
            return True
        print(f"    uv tool install failed for {tool.name}; trying a package manager")

    if manager is None:
        return False

    _, prefix = PACKAGE_MANAGERS[manager]
    command = [*prefix, tool.package_for(manager)]
    print(f"    installing {tool.name} via: {' '.join(command)}")
    proc = subprocess.run(command, check=False)  # noqa: S603
    return proc.returncode == 0


def print_manual_instructions(missing: list[Tool]) -> None:
    """Print per-tool documentation links for manual installation."""
    print("\nInstall these manually, then re-run `just doctor`:")
    for tool in missing:
        print(f"  {tool.name:<8} {tool.docs}")


def do_install() -> int:
    """Install missing tools. Returns a process exit code."""
    if not shutil.which("uv"):
        print("error: uv is required and cannot install itself.")
        print("  Install it first: https://docs.astral.sh/uv/getting-started/installation/")
        print("  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh")
        print('  Windows:     powershell -c "irm https://astral.sh/uv/install.ps1 | iex"')
        return 1

    manager = detect_package_manager()
    print(f"Platform: {sys.platform}")
    print(f"Package manager: {manager or 'none detected'}\n")

    failed: list[Tool] = []
    for tool in TOOLS:
        if shutil.which(tool.name):
            print(f"  ok       {tool.name} already installed")
            continue
        label = "required" if tool.required else "optional"
        print(f"  install  {tool.name} ({label})")
        if not install_tool(tool, manager):
            failed.append(tool)
            print(f"    could not install {tool.name} automatically")

    if failed:
        print_manual_instructions(failed)
        if any(tool.required for tool in failed):
            return 1

    # Sync the workspace so server packages are importable. Without this the
    # documented `just install` -> `just check` path fails at collection with
    # ModuleNotFoundError.
    if not sync_workspace():
        print("\nerror: `uv sync --all-packages` failed; the workspace is not usable.")
        return 1
    return 0


def do_doctor(engine: str) -> int:
    """Report toolchain status. Returns a process exit code."""
    status = 0

    print("Required tools")
    for tool in (t for t in TOOLS if t.required):
        version = tool_version(tool)
        if version == "not installed":
            print(f"  {tool.name:<8} MISSING -- run: just install")
            status = 1
        else:
            print(f"  {tool.name:<8} {version}")

    print("\nOptional tools")
    for tool in (t for t in TOOLS if not t.required):
        version = tool_version(tool)
        if version == "not installed":
            print(f"  {tool.name:<8} not installed -- {tool.purpose} unavailable")
        else:
            print(f"  {tool.name:<8} {version}")

    print("\nWorkspace tools (from uv)")
    for name in WORKSPACE_TOOLS:
        if workspace_tool_ok(name):
            print(f"  {name:<8} ok")
        else:
            print(f"  {name:<8} MISSING -- run: just sync")
            status = 1

    servers = discover_server_packages()
    if servers:
        print("\nWorkspace server packages")
        for package, module in servers:
            if server_package_importable(module):
                print(f"  {package:<24} ok")
            else:
                print(f"  {package:<24} NOT INSTALLED -- run: just sync")
                status = 1

    print(f"\nContainer engine ({engine})")
    ready, message = container_engine_status(engine)
    print(f"  {message}")
    if not ready and engine == "podman" and shutil.which("podman"):
        print("  start it with: podman machine init   # first time only")
        print("                 podman machine start")
        if IS_MACOS:
            print("  a libkrun machine also needs: brew tap slp/krun && brew install krunkit")

    print()
    if status != 0:
        print("Some required tooling is missing.")
    elif not ready:
        print("All required tooling present. Start the container engine to build images.")
    else:
        print("All required tooling present and ready.")
    return status


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("doctor", "install"), help="Report status, or install missing tools."
    )
    parser.add_argument(
        "--engine", default="podman", help="Container engine to check (default: podman)."
    )
    args = parser.parse_args(argv)

    if args.action == "install":
        code = do_install()
        if code != 0:
            return code
        print()
    return do_doctor(args.engine)


if __name__ == "__main__":
    raise SystemExit(main())
