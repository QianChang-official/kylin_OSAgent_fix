"""Tests for MCP SSE transport support.

Verifies SSE transport functions exist, behave correctly with and without
the optional MCP SDK, and that the pure-Python MCP adapter still works
independently of the SDK.
"""
import pytest

from backend.mcp_server import create_sse_server, run_sse, _load_sse_transport
from backend.mcp_adapter import list_mcp_tools, call_mcp_tool

try:
    import mcp  # noqa: F401
    MCP_INSTALLED = True
except ImportError:
    MCP_INSTALLED = False


def test_sse_transport_functions_exist():
    assert callable(create_sse_server)
    assert callable(run_sse)


def test_load_sse_transport_without_sdk_raises():
    if MCP_INSTALLED:
        pytest.skip("mcp SDK installed; skip no-SDK behavior test")
    with pytest.raises(RuntimeError, match="MCP SSE transport requires"):
        _load_sse_transport()


def test_create_sse_server_without_sdk_raises():
    if MCP_INSTALLED:
        pytest.skip("mcp SDK installed; skip no-SDK behavior test")
    with pytest.raises((RuntimeError, ImportError)):
        create_sse_server()


@pytest.mark.skipif(not MCP_INSTALLED, reason="requires mcp SDK")
def test_create_sse_server_returns_starlette_app_when_sdk_installed():
    starlette_app = create_sse_server()
    assert starlette_app is not None
    # Starlette app has routes
    assert hasattr(starlette_app, "routes")
    route_paths = []
    for route in starlette_app.routes:
        path = getattr(route, "path", None)
        if path:
            route_paths.append(path)
    assert any("sse" in p for p in route_paths)
    assert any("messages" in p for p in route_paths)


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
