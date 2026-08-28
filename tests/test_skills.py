"""Validates every skill against the Agent Skills specification.

Parametrized across all discovered skills (see ``conftest.py``). Unlike a
substring check, this parses the YAML frontmatter properly and enforces the
constraints from https://agentskills.io/specification:

* ``name``: required, 1-64 chars, lowercase alphanumeric + hyphens, no
  leading/trailing or consecutive hyphens, and must match the directory name.
* ``description``: required, non-empty, <= 1024 chars.
* ``compatibility``: optional, <= 500 chars.
* ``metadata``: optional, string -> string mapping.
* Unknown frontmatter keys are rejected.
"""

from __future__ import annotations

import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

IS_WINDOWS = sys.platform == "win32"

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500

KNOWN_FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}


def parse_frontmatter(skill_md: Path) -> dict[str, Any]:
    """Parse and return the YAML frontmatter block of a ``SKILL.md``."""
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{skill_md} must open with a '---' frontmatter fence"
    _, _, remainder = text.partition("---\n")
    frontmatter_text, fence, _ = remainder.partition("\n---")
    assert fence, f"{skill_md} has an unterminated frontmatter block"

    loaded = yaml.safe_load(frontmatter_text)
    assert isinstance(loaded, dict), f"{skill_md} frontmatter must be a YAML mapping"
    return loaded


@pytest.fixture
def frontmatter(skill_dir: Path) -> dict[str, Any]:
    return parse_frontmatter(skill_dir / "SKILL.md")


def test_skill_directory_contains_skill_md(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    assert skill_md.is_file()
    assert skill_md.stat().st_size > 0, "SKILL.md must not be empty"


def test_frontmatter_has_only_known_keys(skill_dir: Path, frontmatter: dict[str, Any]) -> None:
    unknown = set(frontmatter) - KNOWN_FRONTMATTER_KEYS
    assert not unknown, f"{skill_dir.name}: unknown frontmatter keys {sorted(unknown)}"


def test_skill_name_is_valid_and_matches_directory(
    skill_dir: Path, frontmatter: dict[str, Any]
) -> None:
    name = frontmatter.get("name")
    assert isinstance(name, str), "name is required and must be a string"
    assert name, "name must not be empty"
    assert 1 <= len(name) <= MAX_NAME_LENGTH, f"name must be 1-{MAX_NAME_LENGTH} chars"
    assert SKILL_NAME_PATTERN.match(name), (
        f"{name!r} must be lowercase alphanumeric with single hyphens, "
        "not starting or ending with a hyphen"
    )
    assert name == skill_dir.name, (
        f"frontmatter name {name!r} must match directory {skill_dir.name!r}"
    )


def test_skill_description_is_present_and_bounded(frontmatter: dict[str, Any]) -> None:
    description = frontmatter.get("description")
    assert isinstance(description, str), "description is required and must be a string"
    assert description.strip(), "description must not be empty"
    assert len(description) <= MAX_DESCRIPTION_LENGTH, (
        f"description must be <= {MAX_DESCRIPTION_LENGTH} chars, got {len(description)}"
    )


def test_optional_frontmatter_fields_have_correct_types(
    frontmatter: dict[str, Any],
) -> None:
    if "license" in frontmatter:
        assert isinstance(frontmatter["license"], str)

    if "compatibility" in frontmatter:
        compatibility = frontmatter["compatibility"]
        assert isinstance(compatibility, str)
        assert len(compatibility) <= MAX_COMPATIBILITY_LENGTH

    if "allowed-tools" in frontmatter:
        assert isinstance(frontmatter["allowed-tools"], str)

    if "metadata" in frontmatter:
        metadata = frontmatter["metadata"]
        assert isinstance(metadata, dict), "metadata must be a mapping"
        for key, value in metadata.items():
            assert isinstance(key, str), f"metadata key {key!r} must be a string"
            assert isinstance(value, str), (
                f"metadata value for {key!r} must be a string (quote numbers/versions)"
            )


def _git_index_mode(path: Path) -> str | None:
    """Return the file mode git records for ``path`` (e.g. ``100755``).

    Read from git's index rather than the filesystem so the check means the
    same thing on Windows, which has no POSIX executable bit. Returns ``None``
    for untracked files.
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "ls-files", "--stage", "--", str(path)],  # noqa: S607
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split(maxsplit=1)[0]


def test_bundled_scripts_are_executable(skill_dir: Path) -> None:
    """Skill scripts are invoked directly, so they need the executable bit.

    Checked via git's index mode, which is meaningful on every platform --
    Windows has no POSIX executable bit, but git still records 100755 and
    that is what Linux/macOS contributors will check out.
    """
    scripts = sorted((skill_dir / "scripts").glob("*.py"))
    if not scripts:
        pytest.skip("skill bundles no scripts")

    not_executable = []
    for script in scripts:
        mode = _git_index_mode(script)
        if mode is None:
            # Untracked (e.g. freshly scaffolded): fall back to the filesystem,
            # which is only meaningful off Windows.
            if not IS_WINDOWS and not script.stat().st_mode & stat.S_IXUSR:
                not_executable.append(script.name)
        elif not mode.endswith("755"):
            not_executable.append(f"{script.name} (git mode {mode})")

    assert not not_executable, (
        f"{skill_dir.name}: scripts are not executable: {not_executable}\n"
        "Fix with: git update-index --chmod=+x <path>  (or chmod +x on Unix)"
    )


def test_bundled_scripts_have_a_shebang(skill_dir: Path) -> None:
    scripts = sorted((skill_dir / "scripts").glob("*.py"))
    if not scripts:
        pytest.skip("skill bundles no scripts")

    missing = [s.name for s in scripts if not s.read_text(encoding="utf-8").startswith("#!")]
    assert not missing, f"{skill_dir.name}: scripts missing a shebang line: {missing}"


def test_bundled_scripts_use_lf_line_endings(skill_dir: Path) -> None:
    """A CRLF after the shebang makes the interpreter unparsable on Unix.

    `.gitattributes` forces LF for `*.py`; this catches a file that slipped in
    before that was in place, or one added with `-c core.autocrlf=true`.
    """
    scripts = sorted((skill_dir / "scripts").glob("*.py"))
    if not scripts:
        pytest.skip("skill bundles no scripts")

    crlf = [s.name for s in scripts if b"\r\n" in s.read_bytes()]
    assert not crlf, (
        f"{skill_dir.name}: scripts contain CRLF line endings: {crlf}. "
        "These must be LF; see .gitattributes."
    )


def test_referenced_scripts_exist(skill_dir: Path) -> None:
    """Every ``./scripts/...`` path mentioned in SKILL.md must exist."""
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    referenced = set(re.findall(r"\./(scripts/[\w./-]+)", text))
    missing = sorted(ref for ref in referenced if not (skill_dir / ref).exists())
    assert not missing, f"{skill_dir.name}: SKILL.md references missing files: {missing}"
