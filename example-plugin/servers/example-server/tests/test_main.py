"""Tests for the console entrypoint (``python -m example_server``).

`mcp.run` is monkeypatched so these tests verify the environment-variable
wiring in ``__main__.py`` without ever binding a real socket or starting an
HTTP server.
"""

from __future__ import annotations

from unittest.mock import patch

import example_server.__main__ as entrypoint
import pytest


class TestSplitEnvList:
    """Test `_split_env_list`'s comma-separated parsing."""

    def test_returns_none_when_the_variable_is_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FASTMCP_ALLOWED_HOSTS", raising=False)
        assert entrypoint._split_env_list("FASTMCP_ALLOWED_HOSTS") is None

    def test_returns_none_for_an_empty_or_whitespace_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FASTMCP_ALLOWED_HOSTS", "   ")
        assert entrypoint._split_env_list("FASTMCP_ALLOWED_HOSTS") is None

    def test_splits_and_strips_a_comma_separated_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FASTMCP_ALLOWED_HOSTS", "example.com, api.example.com ,  ")
        assert entrypoint._split_env_list("FASTMCP_ALLOWED_HOSTS") == [
            "example.com",
            "api.example.com",
        ]


class TestMain:
    """Test `main`'s environment-to-transport-kwargs wiring."""

    def test_uses_default_host_port_and_path_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in (
            "FASTMCP_HOST",
            "FASTMCP_PORT",
            "FASTMCP_PATH",
            "FASTMCP_ALLOWED_HOSTS",
            "FASTMCP_ALLOWED_ORIGINS",
        ):
            monkeypatch.delenv(name, raising=False)

        with patch.object(entrypoint.mcp, "run") as run:
            entrypoint.main()

        run.assert_called_once_with(transport="http", host="127.0.0.1", port=8000, path="/mcp")

    def test_reads_host_port_and_path_from_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FASTMCP_HOST", "0.0.0.0")  # noqa: S104
        monkeypatch.setenv("FASTMCP_PORT", "9000")
        monkeypatch.setenv("FASTMCP_PATH", "/custom")
        monkeypatch.delenv("FASTMCP_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("FASTMCP_ALLOWED_ORIGINS", raising=False)

        with patch.object(entrypoint.mcp, "run") as run:
            entrypoint.main()

        run.assert_called_once_with(
            transport="http",
            host="0.0.0.0",  # noqa: S104
            port=9000,
            path="/custom",
        )

    def test_adds_allowed_hosts_and_origins_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FASTMCP_HOST", raising=False)
        monkeypatch.delenv("FASTMCP_PORT", raising=False)
        monkeypatch.delenv("FASTMCP_PATH", raising=False)
        monkeypatch.setenv("FASTMCP_ALLOWED_HOSTS", "example.com")
        monkeypatch.setenv("FASTMCP_ALLOWED_ORIGINS", "https://example.com")

        with patch.object(entrypoint.mcp, "run") as run:
            entrypoint.main()

        kwargs = run.call_args.kwargs
        assert kwargs["allowed_hosts"] == ["example.com"]
        assert kwargs["allowed_origins"] == ["https://example.com"]

    def test_omits_allowlists_entirely_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FASTMCP_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("FASTMCP_ALLOWED_ORIGINS", raising=False)

        with patch.object(entrypoint.mcp, "run") as run:
            entrypoint.main()

        kwargs = run.call_args.kwargs
        assert "allowed_hosts" not in kwargs
        assert "allowed_origins" not in kwargs
