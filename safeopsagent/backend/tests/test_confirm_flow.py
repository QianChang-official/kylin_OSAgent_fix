import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.app import app
from backend.security.guardrail import Guardrail
from backend.security.risk_score import RiskScoreResult
from backend.tools.registry import ToolResult, get_registry


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_confirmations():
    app_module._confirmations.clear()
    yield
    app_module._confirmations.clear()


def _tool_success(name, args):
    return ToolResult(
        tool=name,
        status="success",
        data={"confirmed": True, "args": args},
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
        matched_rules=["test_confirm_rule"],
        factors=["test_confirm_factor"],
    )


def _force_confirm(monkeypatch):
    monkeypatch.setattr(
        Guardrail,
        "score_100",
        lambda self, **kwargs: _risk_result(),
    )


def test_tools_call_allow_still_executes(monkeypatch):
    called = {"count": 0}

    def fake_call(name, args):
        called["count"] += 1
        return _tool_success(name, args)

    monkeypatch.setattr(get_registry(), "call", fake_call)

    response = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["security_decision"] == "allow"
    assert body["confirmation_required"] is False
    assert body["confirmation_token"] is None
    assert called["count"] == 1


def test_tools_call_reject_still_blocks_without_token(monkeypatch):
    called = {"count": 0}
    monkeypatch.setattr(get_registry(), "call", lambda name, args: called.update(count=called["count"] + 1))

    response = client.post(
        "/tools/call",
        json={"tool_name": "large_file_scan", "arguments": {"path": "/etc/passwd", "size": "+1K"}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["confirmation_token"] is None
    assert called["count"] == 0


def test_tools_call_confirm_returns_token_and_dry_run(monkeypatch):
    _force_confirm(monkeypatch)
    called = {"count": 0}
    monkeypatch.setattr(get_registry(), "call", lambda name, args: called.update(count=called["count"] + 1))

    response = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "confirm"
    assert body["confirmation_required"] is True
    assert body["confirmation_token"]
    assert body["dry_run_result"]["tool_name"] == "get_memory_status"
    assert body["dry_run_result"]["message"] == "该操作需要人工确认，尚未执行。"
    assert called["count"] == 0


def test_tools_confirm_valid_token_executes_once(monkeypatch):
    _force_confirm(monkeypatch)
    called = {"count": 0}

    def fake_call(name, args):
        called["count"] += 1
        return _tool_success(name, args)

    monkeypatch.setattr(get_registry(), "call", fake_call)
    initial = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}}).json()

    confirmed = client.post(
        "/tools/confirm",
        json={"confirmation_token": initial["confirmation_token"], "session_id": "confirm-test"},
    ).json()
    repeated = client.post(
        "/tools/confirm",
        json={"confirmation_token": initial["confirmation_token"], "session_id": "confirm-test"},
    ).json()

    assert confirmed["success"] is True
    assert confirmed["original_request_id"] == initial["request_id"]
    assert confirmed["result"]["data"]["confirmed"] is True
    assert called["count"] == 1
    assert repeated["success"] is False
    assert repeated["security_reason"] == "confirmation_token_used"
    assert called["count"] == 1


def test_tools_confirm_does_not_expose_execution_exception(monkeypatch):
    _force_confirm(monkeypatch)
    initial = client.post(
        "/tools/call",
        json={"tool_name": "get_memory_status", "arguments": {}},
    ).json()

    def explode(name, args):
        raise RuntimeError("secret backend path: /srv/private/tool.py")

    monkeypatch.setattr(get_registry(), "call", explode)
    body = client.post(
        "/tools/confirm",
        json={"confirmation_token": initial["confirmation_token"]},
    ).json()

    assert body["success"] is False
    assert body["security_reason"] == "tool_exception"
    assert body["error"] == "Tool execution failed"
    assert "private" not in str(body)


def test_tools_confirm_concurrent_replay_executes_once(monkeypatch):
    _force_confirm(monkeypatch)
    called = {"count": 0}

    class _Logger:
        def log(self, entry):
            return True

    def fake_call(name, args):
        called["count"] += 1
        time.sleep(0.05)
        return _tool_success(name, args)

    monkeypatch.setattr(app_module, "get_logger", lambda: _Logger())
    monkeypatch.setattr(get_registry(), "call", fake_call)
    initial = app_module.call_tool(
        app_module.ToolCallRequest(tool_name="get_memory_status", arguments={})
    )
    request = app_module.ToolConfirmRequest(
        confirmation_token=initial["confirmation_token"],
        session_id="concurrent-replay",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: app_module.confirm_tool(request), range(2)))

    assert sum(response["success"] is True for response in responses) == 1
    assert sum(
        response["security_reason"] == "confirmation_token_used"
        for response in responses
    ) == 1
    assert called["count"] == 1


def test_tools_confirm_expired_token_does_not_execute(monkeypatch):
    _force_confirm(monkeypatch)
    called = {"count": 0}
    monkeypatch.setattr(get_registry(), "call", lambda name, args: called.update(count=called["count"] + 1) or _tool_success(name, args))
    initial = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}}).json()
    app_module._confirmations[initial["confirmation_token"]]["expires_at"] = time.time() - 1

    response = client.post("/tools/confirm", json={"confirmation_token": initial["confirmation_token"]})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_reason"] == "confirmation_token_expired"
    assert called["count"] == 0


def test_reject_token_cannot_be_confirmed(monkeypatch):
    called = {"count": 0}
    monkeypatch.setattr(get_registry(), "call", lambda name, args: called.update(count=called["count"] + 1) or _tool_success(name, args))
    app_module._confirmations["reject-token"] = {
        "original_request_id": "orig-reject",
        "session_id": "s1",
        "tool_name": "get_memory_status",
        "arguments": {},
        "risk_score": 100,
        "risk_level": "forbidden",
        "legacy_risk_level": 5,
        "security_decision": "reject",
        "security_reason": "blocked_by_guardrail",
        "matched_rules": ["dangerous_cmd:rm"],
        "risk_factors": [],
        "rule_hits": {},
        "created_at": time.time(),
        "expires_at": time.time() + 300,
        "used": False,
    }

    body = client.post("/tools/confirm", json={"confirmation_token": "reject-token"}).json()

    assert body["success"] is False
    assert body["security_reason"] == "confirmation_token_not_confirmable"
    assert called["count"] == 0


def test_confirm_revalidation_rejects_if_risk_changes(monkeypatch):
    _force_confirm(monkeypatch)
    initial = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}}).json()

    monkeypatch.setattr(
        Guardrail,
        "score_100",
        lambda self, **kwargs: _risk_result(100, "forbidden", 5, "reject"),
    )
    called = {"count": 0}
    monkeypatch.setattr(get_registry(), "call", lambda name, args: called.update(count=called["count"] + 1) or _tool_success(name, args))

    body = client.post("/tools/confirm", json={"confirmation_token": initial["confirmation_token"]}).json()

    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "blocked_by_guardrail"
    assert called["count"] == 0


def test_audit_trace_records_confirmation_events(monkeypatch):
    _force_confirm(monkeypatch)
    monkeypatch.setattr(get_registry(), "call", _tool_success)

    initial = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}}).json()
    confirmed = client.post(
        "/tools/confirm",
        json={"confirmation_token": initial["confirmation_token"], "session_id": "confirm-trace"},
    ).json()

    initial_trace = client.get(f"/audit/trace/{initial['request_id']}").json()
    confirmed_trace = client.get(f"/audit/trace/{confirmed['request_id']}").json()
    initial_events = {event["stage"]: event for event in initial_trace["trace"]["events"]}
    confirmed_events = {event["stage"]: event for event in confirmed_trace["trace"]["events"]}

    assert initial_events["confirmation"]["events"] == ["confirmation_requested"]
    assert confirmed_events["confirmation"]["events"] == ["confirmation_approved"]
    assert confirmed_trace["trace"]["original_request_id"] == initial["request_id"]
    assert confirmed["original_request_id"] == initial["request_id"]
    assert initial["confirmation_token"] not in json.dumps(
        confirmed_trace,
        ensure_ascii=False,
        default=str,
    )
