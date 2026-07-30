"""Optional stdio MCP server for SafeOpsAgent.

Install optional dependencies from ``backend/requirements-mcp.txt`` before
running this module. The default FastAPI backend does not import the MCP SDK.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.mcp_adapter import call_mcp_tool, list_mcp_tools


SERVER_NAME = "safeopsagent"
SERVER_VERSION = "1.3.0"


def create_server():
    """Create an MCP Server instance if the optional SDK is installed."""
    Server, types = _load_server_types()
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def handle_list_tools():
        return [
            types.Tool(
                name=tool["name"],
                description=tool.get("description", ""),
                inputSchema=tool.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for tool in list_mcp_tools()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None):
        result = call_mcp_tool(name, arguments or {})
        return _to_call_tool_result(types, result)

    return server


async def run_stdio() -> None:
    """Run the SafeOpsAgent MCP server over stdio."""
    Server, types = _load_server_types()
    NotificationOptions, InitializationOptions, stdio_server = _load_runtime_types()
    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def create_sse_server():
    """Create a Starlette app exposing the MCP server over SSE transport.

    This lets external MCP clients connect to SafeOpsAgent via SSE/HTTP
    instead of stdio, so the FastAPI service can host REST API, Vue
    console and MCP SSE on the same origin. Requires the optional MCP
    SDK (backend/requirements-mcp.txt).
    """
    Server, types = _load_server_types()
    NotificationOptions, InitializationOptions, _ = _load_runtime_types()
    SseServerTransport = _load_sse_transport()
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    server = create_server()
    sse = SseServerTransport("/mcp/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(
                streams[0],
                streams[1],
                InitializationOptions(
                    server_name=SERVER_NAME,
                    server_version=SERVER_VERSION,
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
        return Response()

    return Starlette(routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ])


async def run_sse(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the SafeOpsAgent MCP server over SSE as a standalone uvicorn app."""
    import uvicorn

    starlette_app = create_sse_server()
    config = uvicorn.Config(starlette_app, host=host, port=port, log_level="info")
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


def _load_sse_transport():
    try:
        from mcp.server.sse import SseServerTransport
    except ImportError as exc:
        raise RuntimeError(
            "MCP SSE transport requires the optional mcp SDK. "
            "Install backend/requirements-mcp.txt first."
        ) from exc
    return SseServerTransport


def main() -> None:
    try:
        asyncio.run(run_stdio())
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def _load_server_types():
    try:
        from mcp.server import Server
        import mcp.types as types
    except ImportError as exc:
        raise RuntimeError(
            "Optional MCP SDK is not installed. Install backend/requirements-mcp.txt "
            "and run: python -m backend.mcp_server"
        ) from exc
    return Server, types


def _load_runtime_types():
    try:
        from mcp.server import NotificationOptions
        from mcp.server.models import InitializationOptions
        from mcp.server.stdio import stdio_server
    except ImportError as exc:
        raise RuntimeError(
            "Optional MCP SDK runtime imports failed. Check backend/requirements-mcp.txt."
        ) from exc
    return NotificationOptions, InitializationOptions, stdio_server


def _to_call_tool_result(types, result: dict[str, Any]):
    text = json.dumps(result, ensure_ascii=False, default=str)
    is_error = _is_error_result(result)
    content = [types.TextContent(type="text", text=text)]
    try:
        return types.CallToolResult(
            content=content,
            structuredContent=result,
            isError=is_error,
        )
    except TypeError:
        return types.CallToolResult(content=content, isError=is_error)


def _is_error_result(result: dict[str, Any]) -> bool:
    if result.get("security_decision") == "confirm":
        return False
    return result.get("success") is False


if __name__ == "__main__":
    main()
