"""INV-R2 x INV-R4: no entry point executes a tool it cannot record.

/chat, /tools/call and both MCP transports converge on the same guardrail.
They must also converge on the same audit precondition, otherwise the weakest
entry point becomes the way to act without leaving a record. Each case below
drives a real request with the audit store made unwritable and asserts the
request is refused rather than served.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.audit import logger as logger_module
from backend.tools.registry import ToolResult, get_registry


client = TestClient(app)


@pytest.fixture
def unwritable_audit(tmp_path, monkeypatch):
    """Point the shared logger at a path SQLite cannot open."""
    broken = tmp_path / "audit-is-a-directory"
    broken.mkdir()
    monkeypatch.setattr(logger_module.get_logger(), "db_path", broken)
    return broken


@pytest.fixture
def executable_tool(monkeypatch):
    """A tool that would succeed, so a refusal can only come from the audit gate."""
    executed = []

    def _call(name, args):
        executed.append(name)
        return ToolResult(tool=name, status="success", data={"ok": True}, raw_output="ok")

    monkeypatch.setattr(get_registry(), "call", _call)
    return executed


def test_chat_refuses_when_audit_is_unwritable(unwritable_audit, executable_tool):
    response = client.post(
        "/chat", json={"session_id": "audit-down", "message": "check memory status"}
    )

    assert response.status_code == 503
    assert "Audit log is unavailable" in response.json()["detail"]
    assert executed_nothing(executable_tool)


def test_tools_call_refuses_when_audit_is_unwritable(unwritable_audit, executable_tool):
    response = client.post(
        "/tools/call", json={"tool_name": "get_memory_status", "arguments": {}}
    )

    assert response.status_code == 503
    assert "Audit log is unavailable" in response.json()["detail"]
    assert executed_nothing(executable_tool)


def test_mcp_adapter_refuses_when_audit_is_unwritable(unwritable_audit, executable_tool):
    """The MCP surface delegates to call_tool, so it inherits the same gate."""
    from fastapi import HTTPException

    from backend.mcp_adapter import call_mcp_tool

    with pytest.raises(HTTPException) as excinfo:
        call_mcp_tool("get_memory_status", {})

    assert excinfo.value.status_code == 503
    assert executed_nothing(executable_tool)


def test_healthy_audit_still_executes(executable_tool):
    """The gate must not be a permanent denial."""
    response = client.post(
        "/tools/call", json={"tool_name": "get_memory_status", "arguments": {}}
    )

    assert response.status_code == 200
    assert executable_tool == ["get_memory_status"]


def executed_nothing(executed: list) -> bool:
    return executed == []
