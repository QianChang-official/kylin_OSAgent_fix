from fastapi.testclient import TestClient

from backend import app as app_module
from backend.agent.orchestrator import AgentOrchestrator
from backend.audit.logger import AuditLogger
from backend.tools.registry import ToolResult


def _client_with_orchestrator(monkeypatch, tmp_path):
    orchestrator = AgentOrchestrator()
    orchestrator.audit = AuditLogger(tmp_path / "audit.db")
    monkeypatch.setattr(app_module, "get_orch", lambda: orchestrator)
    return TestClient(app_module.app), orchestrator


def test_http_memory_diagnosis_to_audit_trace(monkeypatch, tmp_path):
    client, orchestrator = _client_with_orchestrator(monkeypatch, tmp_path)
    monkeypatch.setattr(
        orchestrator.llm,
        "chat",
        lambda messages, tools: {
            "tool_plan": [
                {
                    "tool_name": "get_memory_status",
                    "arguments": {},
                    "reason": "Inspect memory pressure.",
                }
            ],
            "intent": "memory_status_query",
            "confidence": 0.9,
        },
    )
    monkeypatch.setattr(
        orchestrator.registry,
        "call",
        lambda name, args: ToolResult(
            tool=name,
            status="success",
            data={
                "total_mb": 8000,
                "used_mb": 3200,
                "free_mb": 1000,
                "available_mb": 4800,
                "swap_total_mb": 2000,
                "swap_used_mb": 20,
            },
            audit={"execution_success": True, "executor_user": "tester"},
        ),
    )

    response = client.post(
        "/chat",
        json={"message": "check memory status", "session_id": "e2e-memory"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["executed"] is True
    assert body["diagnosis"]["severity"] == "normal"
    assert any(
        item["metric"] == "memory_usage_percent" and item["value"] == 40.0
        for item in body["diagnosis"]["evidence"]
    )
    trace = orchestrator.audit.trace(body["request_id"])
    assert trace["found"] is True
    assert any(
        event["stage"] == "result_summarized"
        and event["diagnosis_severity"] == "normal"
        for event in trace["trace"]["events"]
    )


def test_http_high_risk_rejected_before_planner_and_traced(monkeypatch, tmp_path):
    client, orchestrator = _client_with_orchestrator(monkeypatch, tmp_path)
    planner_calls = {"count": 0}

    def forbidden_planner(*args, **kwargs):
        planner_calls["count"] += 1
        raise AssertionError("planner must not receive high-risk input")

    monkeypatch.setattr(orchestrator.llm, "chat", forbidden_planner)
    response = client.post(
        "/chat",
        json={"message": "rm -rf /", "session_id": "e2e-reject"},
    )
    body = response.json()

    assert response.status_code == 200
    assert planner_calls["count"] == 0
    assert body["risk_score"] == 100
    assert body["security_decision"] == "reject"
    assert body["executed"] is False
    trace = orchestrator.audit.trace(body["request_id"])
    assert trace["found"] is True
    assert any(
        event["stage"] == "security_decision"
        and event["security_decision"] == "reject"
        for event in trace["trace"]["events"]
    )
