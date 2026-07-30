import pytest
import asyncio
import os
import sys
from pathlib import Path


def test_optional_mcp_server_can_be_created_when_sdk_installed():
    pytest.importorskip("mcp")

    from backend.mcp_server import create_server

    assert create_server() is not None


def test_optional_mcp_stdio_initialize_list_and_call_interoperability():
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    project_root = Path(__file__).resolve().parents[2]

    async def verify():
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(project_root)
        environment["MODEL_PROVIDER"] = "offline_safe"
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "backend.mcp_server"],
            env=environment,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "safeopsagent"
                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                assert "get_memory_status" in names
                assert "get_cpu_status" in names
                assert "safe_cleanup_plan" in names
                called = await session.call_tool("get_memory_status", arguments={})
                assert called.content

    asyncio.run(verify())
