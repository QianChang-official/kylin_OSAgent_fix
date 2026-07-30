"""Tests for MCP SSE transport support.

Verifies SSE transport functions exist, behave correctly with and without
the optional MCP SDK, and that the pure-Python MCP adapter still works
independently of the SDK.
"""
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from backend import app as app_module
from backend import mcp_server
from backend.mcp_server import mount_sse_server, run_sse, _load_sse_transport
from backend.mcp_adapter import list_mcp_tools, call_mcp_tool

try:
    import mcp  # noqa: F401
    MCP_INSTALLED = True
except ImportError:
    MCP_INSTALLED = False


def test_sse_transport_functions_exist():
    assert callable(mount_sse_server)
    assert callable(run_sse)
    assert not hasattr(mcp_server, "create_sse_server")


def test_load_sse_transport_without_sdk_raises():
    if MCP_INSTALLED:
        pytest.skip("mcp SDK installed; skip no-SDK behavior test")
    with pytest.raises(RuntimeError, match="MCP SSE transport requires"):
        _load_sse_transport()


def test_mount_sse_server_without_sdk_raises():
    if MCP_INSTALLED:
        pytest.skip("mcp SDK installed; skip no-SDK behavior test")
    parent = FastAPI()
    parent.add_middleware(BaseHTTPMiddleware, dispatch=app_module.enforce_console_auth)
    with pytest.raises((RuntimeError, ImportError)):
        mount_sse_server(parent)


def test_http_mcp_requires_parent_authentication_boundary():
    parent = FastAPI()
    with pytest.raises(RuntimeError, match="authenticated FastAPI"):
        mount_sse_server(parent)


@pytest.mark.skipif(not MCP_INSTALLED, reason="requires mcp SDK")
def test_mount_sse_server_mounts_under_authenticated_parent_when_sdk_installed():
    parent = FastAPI()
    parent.add_middleware(BaseHTTPMiddleware, dispatch=app_module.enforce_console_auth)

    mount_sse_server(parent)

    assert any(getattr(route, "path", None) == "/mcp" for route in parent.routes)
    assert TestClient(parent).get("/mcp/not-a-route").status_code == 404


@pytest.mark.skipif(not MCP_INSTALLED, reason="requires mcp SDK")
def test_private_http_mcp_subapp_rejects_direct_requests():
    child = mcp_server._create_sse_server()

    response = TestClient(child).get("/sse")

    assert response.status_code == 403
    assert response.json()["detail"] == "HTTP MCP requires the authenticated FastAPI parent"


def test_standalone_http_mcp_is_disabled():
    with pytest.raises(RuntimeError, match="Standalone HTTP MCP is disabled"):
        asyncio.run(run_sse())


def test_mcp_adapter_list_tools_includes_config_drift():
    """Pure-Python adapter must list all registered tools including config_drift_check."""
    tools = list_mcp_tools()
    assert len(tools) > 0
    names = [tool["name"] for tool in tools]
    assert "config_drift_check" in names
    assert "get_memory_status" in names
    assert "large_file_scan" in names


def test_mcp_adapter_list_tools_includes_confirm_tool():
    tools = list_mcp_tools(include_confirm_tool=True)
    names = [tool["name"] for tool in tools]
    assert "safeops_confirm_tool" in names


def test_mcp_adapter_call_unknown_tool_returns_error():
    result = call_mcp_tool("nonexistent_tool_xyz", {})
    assert isinstance(result, dict)
    # 未知工具应被安全链路拦截或返回错误
    assert result.get("success") is False or result.get("security_decision") in {"reject", "no_action"}
