import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from backend.app import app
from backend.audit.logger import AuditLogger
from backend.tools.registry import ToolResult, get_registry


client = TestClient(app)


def test_audit_logger_adds_v2_columns_to_existing_table(tmp_path):
    db_path = tmp_path / "audit.db"
    table_name = f"audit_{datetime.now().strftime('%Y%m%d')}"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                session_id TEXT,
                request_id TEXT,
                user_input TEXT,
                intent TEXT,
                selected_tool TEXT,
                tool_arguments TEXT,
                risk_level INTEGER,
                confirmation_required INTEGER,
                executed INTEGER,
                execution_result TEXT,
                final_response TEXT,
                rule_hits TEXT,
                duration_ms INTEGER
            )
        """)
        conn.commit()

    AuditLogger(db_path)

    with sqlite3.connect(str(db_path)) as conn:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}

    assert "risk_score" in columns
    assert "risk_level_text" in columns
    assert "security_decision" in columns
    assert "actual_command" in columns
    assert "full_trace_json" in columns


def test_tools_call_writes_trace_v2(monkeypatch):
    monkeypatch.setattr(
        get_registry(),
        "call",
        lambda name, args: ToolResult(
            tool=name,
            status="success",
            data={"total_mb": 16000, "used_mb": 8000},
            raw_output="Mem: 16000 8000",
            audit={
                "actual_command": ["free", "-m"],
                "executor_user": "tester",
                "execution_success": True,
                "stdout_summary": "Mem: 16000 8000",
                "stderr_summary": "",
            },
        ),
    )

    response = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}})
    body = response.json()
    request_id = body["request_id"]

    logs = client.get("/audit/logs").json()["logs"]
    row = next(item for item in logs if item["request_id"] == request_id)

    assert row["risk_score"] == body["risk_score"]
    assert row["risk_level_text"] == body["risk_level"]
    assert row["legacy_risk_level"] == body["legacy_risk_level"]
    assert row["security_decision"] == "allow"
    assert row["security_reason"] == "executed"
    assert row["actual_command"] == ["free", "-m"]
    assert row["executor_user"] == "tester"
    assert row["execution_success"] == 1
    assert "Mem:" in row["stdout_summary"]

    trace = client.get(f"/audit/trace/{request_id}").json()

    assert trace["found"] is True
    assert trace["request_id"] == request_id
    events = {event["stage"]: event for event in trace["trace"]["events"]}
    assert set(events) == {
        "receive_input",
        "precheck",
        "tool_selected",
        "args_validated",
        "risk_scored",
        "security_decision",
        "tool_executed",
        "output_checked",
        "response_generated",
        "audit_saved",
    }
    assert events["tool_executed"]["actual_command"] == ["free", "-m"]
    assert events["tool_executed"]["execution_success"] is True

    clear_response = client.post("/audit/clear").json()
    assert clear_response["status"] == "retained"
    assert client.get(f"/audit/trace/{request_id}").json()["found"] is True


def test_audit_trace_missing_request_id_returns_not_found():
    response = client.get("/audit/trace/not-found-request")
    body = response.json()

    assert response.status_code == 200
    assert body["found"] is False
    assert body["request_id"] == "not-found-request"


def test_audit_logger_is_append_only_and_serializes_safely(tmp_path):
    db_path = tmp_path / "audit.db"
    logger = AuditLogger(db_path)

    class NotJson:
        def __str__(self):
            return "not-json-object"

    assert logger.log({
        "request_id": "safe-json",
        "session_id": "s1",
        "user_input": "x" * 3000,
        "tool_arguments": {"bad": NotJson()},
        "execution_result": {"items": {1, 2, 3}},
        "matched_rules": [NotJson()],
        "stdout_summary": "o" * 3000,
        "stderr_summary": "e" * 3000,
        "final_response": "r" * 3000,
    }) is True

    before = logger.trace("safe-json")
    assert before["found"] is True

    clear_result = logger.clear_all()
    assert clear_result["status"] == "retained"

    after = logger.trace("safe-json")
    assert after["found"] is True
    assert len(after["audit"]["stdout_summary"]) <= 2014
    assert len(after["audit"]["stderr_summary"]) <= 2014
