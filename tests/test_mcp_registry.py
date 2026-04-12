"""Unit tests for ExternalMCPRegistry.

Uses unittest.mock to patch httpx.AsyncClient, simulating a real MCP server
without network access.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from beever_atlas.agents.mcp_registry import ExternalMCPRegistry, _MCPServerConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_TOOLS_RESPONSE = {
    "tools": [
        {"name": "get_doc", "description": "Fetch a document by ID"},
        {"name": "search_index", "description": "Search the document index"},
    ]
}


def _make_mock_client(get_response_json: dict):
    """Return a context-manager mock for httpx.AsyncClient.

    GET requests return `get_response_json`.
    POST requests return {"ok": True}.
    """
    mock_resp_get = MagicMock()
    mock_resp_get.json.return_value = get_response_json
    mock_resp_get.raise_for_status = MagicMock()

    mock_resp_post = MagicMock()
    mock_resp_post.json.return_value = {"ok": True}
    mock_resp_post.raise_for_status = MagicMock()

    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp_get)
    client.post = AsyncMock(return_value=mock_resp_post)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------


def test_from_env_empty_returns_no_op_registry(monkeypatch):
    monkeypatch.setenv("EXTERNAL_MCP_SERVERS", "")
    reg = ExternalMCPRegistry.from_env()
    assert reg.is_empty
    assert reg.tools == []


def test_from_env_invalid_json_logs_warning_and_returns_empty(monkeypatch):
    monkeypatch.setenv("EXTERNAL_MCP_SERVERS", "not-json")
    from unittest.mock import patch as mpatch

    with mpatch("beever_atlas.agents.mcp_registry.logger") as mock_log:
        reg = ExternalMCPRegistry.from_env()
    assert reg.is_empty
    mock_log.warning.assert_called_once()
    warning_msg = mock_log.warning.call_args[0][0]
    assert "failed to parse" in warning_msg.lower()


def test_from_env_non_array_json_returns_empty(monkeypatch):
    monkeypatch.setenv("EXTERNAL_MCP_SERVERS", '{"name": "x"}')
    from unittest.mock import patch as mpatch

    with mpatch("beever_atlas.agents.mcp_registry.logger") as mock_log:
        reg = ExternalMCPRegistry.from_env()
    assert reg.is_empty
    mock_log.warning.assert_called_once()


def test_from_env_valid_parses_configs(monkeypatch):
    servers = [{"name": "svc1", "url": "http://svc1:8080", "auth_token": "tok"}]
    monkeypatch.setenv("EXTERNAL_MCP_SERVERS", json.dumps(servers))
    reg = ExternalMCPRegistry.from_env()
    assert len(reg._configs) == 1
    assert reg._configs[0].name == "svc1"
    assert reg._configs[0].url == "http://svc1:8080"
    assert reg._configs[0].auth_token == "tok"


# ---------------------------------------------------------------------------
# connect — mock httpx.AsyncClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_wraps_tools_from_mock_server():
    """Registry connects to a mock MCP server, fetches tool list, wraps callables."""
    ctx, _ = _make_mock_client(_MOCK_TOOLS_RESPONSE)

    reg = ExternalMCPRegistry(
        _configs=[_MCPServerConfig(name="mocksrv", url="http://mock-mcp:9000")]
    )
    with patch("httpx.AsyncClient", return_value=ctx):
        await reg.connect()

    assert not reg.is_empty
    assert len(reg.tools) == 2
    names = [fn.__name__ for fn in reg.tools]
    assert "mocksrv__get_doc" in names
    assert "mocksrv__search_index" in names


@pytest.mark.asyncio
async def test_connect_skips_unreachable_server():
    """Unreachable server raises — skipped with warning, no exception propagated."""
    from unittest.mock import patch as mpatch

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
    ctx.__aexit__ = AsyncMock(return_value=False)

    reg = ExternalMCPRegistry(
        _configs=[_MCPServerConfig(name="dead", url="http://127.0.0.1:19999")]
    )
    with mpatch("beever_atlas.agents.mcp_registry.logger") as mock_log:
        with patch("httpx.AsyncClient", return_value=ctx):
            await reg.connect()  # must not raise

    assert reg.is_empty
    mock_log.warning.assert_called_once()
    warning_msg = mock_log.warning.call_args[0][0]
    assert "skipping" in warning_msg.lower()


@pytest.mark.asyncio
async def test_connect_empty_config_is_noop():
    reg = ExternalMCPRegistry(_configs=[])
    await reg.connect()  # no exception, no tools
    assert reg.is_empty


# ---------------------------------------------------------------------------
# Wrapped tool callable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wrapped_tool_posts_to_correct_url():
    """Calling the wrapped tool POSTs to /tools/<name> and returns JSON."""
    ctx, _ = _make_mock_client(_MOCK_TOOLS_RESPONSE)

    reg = ExternalMCPRegistry(
        _configs=[_MCPServerConfig(name="mocksrv", url="http://mock-mcp:9000")]
    )
    with patch("httpx.AsyncClient", return_value=ctx):
        await reg.connect()

    get_doc = next(fn for fn in reg.tools if fn.__name__ == "mocksrv__get_doc")

    ctx2, client2 = _make_mock_client({})
    with patch("httpx.AsyncClient", return_value=ctx2):
        await get_doc(doc_id="abc123")

    client2.post.assert_called_once()
    call_url = client2.post.call_args[0][0]
    assert call_url.endswith("/tools/get_doc")


@pytest.mark.asyncio
async def test_wrapped_tool_carries_description():
    ctx, _ = _make_mock_client(_MOCK_TOOLS_RESPONSE)

    reg = ExternalMCPRegistry(
        _configs=[_MCPServerConfig(name="mocksrv", url="http://mock-mcp:9000")]
    )
    with patch("httpx.AsyncClient", return_value=ctx):
        await reg.connect()

    get_doc = next(fn for fn in reg.tools if fn.__name__ == "mocksrv__get_doc")
    assert "Fetch a document by ID" in get_doc.__doc__
    assert "mocksrv" in get_doc.__doc__
