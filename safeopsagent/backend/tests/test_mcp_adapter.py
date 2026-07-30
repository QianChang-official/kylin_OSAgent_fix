import pytest

from backend import app as app_module
from backend.mcp_adapter import CONFIRM_TOOL_NAME, call_mcp_tool, list_mcp_tools
from backend.security.guardrail import Guardrail
from backend.security.risk_score import RiskScoreResult
from backend.tools.registry import ToolResult, get_registry


@pytest.fixture(autouse=True)
def clear_confirmations():
    app_module._confirmations.clear()
    yield
    app_module._confirmations.clear()


def _tool_success(name, args):
    return ToolResult(
        tool=name,
        status="success",
        data={"mcp": True, "args": args},
        raw_output="ok",
    )


def _risk_result(score=70, level="high", legacy=4, decision="confirm"):
    return RiskScoreResult(
        score=score,
        risk_level=level,
        legacy_risk_level=legacy,
        security_decision=decision,
        confirmation_required=decision == "confirm",
        blocked=decision == "reject",
        matched_rules=["test_mcp_confirm_rule"],
        factors=["test_mcp_confirm_factor"],
    )


def _force_confirm(monkeypatch):
    monkeypatch.setattr(
        Guardrail,
        "score_100",
        lambda self, **kwargs: _risk_result(),
    )


def test_list_mcp_tools_contains_current_os_tools_and_confirm_tool():
    tools = list_mcp_tools()
    names = {tool["name"] for tool in tools}

    assert {
        "disk_usage",
        "process_list",
        "network_status",
        "journal_query",
        "large_file_scan",
        "get_port_usage",
        "get_memory_status",
        "get_service_status",
        "get_cpu_status",
        "safe_cleanup_scan",
        "safe_cleanup_plan",
        "safe_cleanup_quarantine",
        "safe_cleanup_restore",
    }.issubset(names)
    assert CONFIRM_TOOL_NAME in names


def test_low_risk_mcp_call_enters_existing_tools_call_chain(monkeypatch):
    called = {"count": 0, "name": "", "args": None}

    def fake_call(name, args):
        called.update(count=called["count"] + 1, name=name, args=args)
        return _tool_success(name, args)

    monkeypatch.setattr(get_registry(), "call", fake_call)

    body = call_mcp_tool("get_memory_status", {"session_id": "mcp-test"})

    assert body["success"] is True
    assert body["request_id"]
    assert body["security_decision"] == "allow"
    assert body["result"]["data"]["mcp"] is True
    assert called["count"] == 1
    assert called["name"] == "get_memory_status"
    assert called["args"] == {}


def test_reject_input_cannot_execute_through_mcp(monkeypatch):
    called = {"count": 0}

    def fake_call(name, args):
        called["count"] += 1
        return _tool_success(name, args)

    monkeypatch.setattr(get_registry(), "call", fake_call)

    body = call_mcp_tool("large_file_scan", {"path": "/etc/passwd", "size": "+1K"})

    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "blocked_by_guardrail"
    assert called["count"] == 0


def test_confirm_mcp_call_returns_token_and_dry_run_without_execution(monkeypatch):
    _force_confirm(monkeypatch)
    called = {"count": 0}
    monkeypatch.setattr(
        get_registry(),
        "call",
        lambda name, args: called.update(count=called["count"] + 1) or _tool_success(name, args),
    )

    body = call_mcp_tool("get_memory_status", {})

    assert body["success"] is False
    assert body["security_decision"] == "confirm"
    assert body["confirmation_required"] is True
    assert body["confirmation_token"]
    assert body["dry_run_result"]["tool_name"] == "get_memory_status"
    assert called["count"] == 0


def test_safeops_confirm_tool_uses_existing_confirm_chain(monkeypatch):
    _force_confirm(monkeypatch)
    called = {"count": 0}

    def fake_call(name, args):
        called["count"] += 1
        return _tool_success(name, args)

    monkeypatch.setattr(get_registry(), "call", fake_call)
    initial = call_mcp_tool("get_memory_status", {})

    confirmed = call_mcp_tool(
        CONFIRM_TOOL_NAME,
        {
            "confirmation_token": initial["confirmation_token"],
            "session_id": "mcp-confirm",
        },
    )

    assert confirmed["success"] is True
    assert confirmed["original_request_id"] == initial["request_id"]
    assert confirmed["security_decision"] == "allow"
    assert confirmed["result"]["data"]["mcp"] is True
    assert called["count"] == 1
