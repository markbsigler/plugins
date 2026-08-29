"""Unit tests for scripts/update_schemas.py.

`urllib.request.urlopen` is mocked so these tests never make a real network
call and never depend on the canonical schema content or endpoint uptime.
"""

from __future__ import annotations

import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from discovery import REPO_ROOT as TEST_REPO_ROOT

sys.path.insert(0, str(TEST_REPO_ROOT / "scripts"))

import update_schemas


def _fake_response(status: int = 200, body: bytes = b"{}") -> MagicMock:
    response = MagicMock()
    response.status = status
    response.read.return_value = body
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """Point `update_schemas.REPO_ROOT` at a scratch directory."""
    monkeypatch.setattr(update_schemas, "REPO_ROOT", tmp_path)
    return tmp_path


def test_fetches_both_schemas_to_the_default_version_directory(fake_repo: Path) -> None:
    responses = [_fake_response(body=b'{"plugin": true}'), _fake_response(body=b'{"mcp": true}')]
    with patch.object(update_schemas.urllib.request, "urlopen", side_effect=responses):
        assert update_schemas.main([]) == 0

    destination = fake_repo / "schemas" / "1.0.0"
    assert (destination / "plugin.schema.json").read_bytes() == b'{"plugin": true}'
    assert (destination / "mcp.schema.json").read_bytes() == b'{"mcp": true}'


def test_uses_a_custom_version_argument(fake_repo: Path) -> None:
    responses = [_fake_response(), _fake_response()]
    with patch.object(update_schemas.urllib.request, "urlopen", side_effect=responses) as urlopen:
        assert update_schemas.main(["2.0.0"]) == 0

    assert (fake_repo / "schemas" / "2.0.0" / "plugin.schema.json").exists()
    requested_url = urlopen.call_args_list[0][0][0]
    assert "2.0.0" in requested_url


def test_returns_one_on_a_non_200_status_without_writing_the_file(fake_repo: Path) -> None:
    with patch.object(
        update_schemas.urllib.request, "urlopen", return_value=_fake_response(status=404)
    ):
        assert update_schemas.main([]) == 1
    assert not (fake_repo / "schemas" / "1.0.0" / "plugin.schema.json").exists()


def test_returns_one_when_the_request_raises_a_url_error(fake_repo: Path) -> None:
    with patch.object(
        update_schemas.urllib.request, "urlopen", side_effect=urllib.error.URLError("no network")
    ):
        assert update_schemas.main([]) == 1
    # The destination directory is created before any fetch is attempted.
    assert (fake_repo / "schemas" / "1.0.0").is_dir()


def test_stops_after_the_first_schema_fails_and_leaves_the_first_written(fake_repo: Path) -> None:
    responses = [_fake_response(body=b"ok"), urllib.error.URLError("boom")]
    with patch.object(update_schemas.urllib.request, "urlopen", side_effect=responses):
        assert update_schemas.main([]) == 1

    destination = fake_repo / "schemas" / "1.0.0"
    assert (destination / "plugin.schema.json").read_bytes() == b"ok"
    assert not (destination / "mcp.schema.json").exists()
