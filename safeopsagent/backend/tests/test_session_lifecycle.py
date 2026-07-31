from fastapi.testclient import TestClient

from backend import app as app_module
from backend import config
from backend.agent.orchestrator import AgentOrchestrator
from backend.app import app
from backend.audit.logger import AuditLogger
from backend.tools.registry import ToolResult

client = TestClient(app)


class FakeLLM:
    def __init__(self):
        self.messages = []

    def chat(self, messages, tools):
        self.messages.append(list(messages))
        return {"tool": "get_memory_status", "args": {}, "reason": "test"}

    def summarize(self, text, max_chars=500):
        return "summary"


def _success_result(name, args):
    return ToolResult(
        tool=name,
        status="success",
        data={"total_mb": 16000, "used_mb": 8000},
        raw_output="Mem: 16000 8000",
    )


def _make_orchestrator(monkeypatch, tmp_path=None):
    orch = AgentOrchestrator()
    orch.llm = FakeLLM()
    monkeypatch.setattr(orch.registry, "call", _success_result)
    if tmp_path is not None:
        orch.audit = AuditLogger(tmp_path / "audit.db")
    return orch


def test_session_keeps_context_before_ttl(monkeypatch):
    orch = _make_orchestrator(monkeypatch)

    first = orch.run("ttl-active", "first")
    second = orch.run("ttl-active", "second")

    assert first["session_events"] == []
    assert second["session_events"] == []
    second_messages = orch.llm.messages[1]
    assert {"role": "user", "content": "first"} in second_messages
    assert {"role": "assistant", "content": first["response"]} in second_messages


def test_session_timeout_resets_context(monkeypatch):
    orch = _make_orchestrator(monkeypatch)
    session_id = "ttl-expired"

    orch.run(session_id, "first")
    orch._session_meta[session_id]["last_seen"] -= config.SESSION_TTL_SECONDS + 1
    result = orch.run(session_id, "second")

    assert result["session_events"] == ["session_expired", "session_reset"]
    assert orch.llm.messages[1] == [{"role": "user", "content": "second"}]
    assert len(orch._sessions[session_id]) == 2


def test_session_max_messages_truncates_context(monkeypatch):
    monkeypatch.setattr(config, "SESSION_MAX_MESSAGES", 4)
    orch = _make_orchestrator(monkeypatch)
    session_id = "ttl-trim"

    last_result = None
    for index in range(4):
        last_result = orch.run(session_id, f"message-{index}")

    assert len(orch._sessions[session_id]) == 4
    assert orch._sessions[session_id][0]["content"] == "message-2"
    assert orch._sessions[session_id][-1]["content"] == last_result["response"]


def test_chat_default_flow_still_works(monkeypatch):
    orch = app_module.get_orch()
    orch.llm.provider = "mock"
    orch.llm.api_key = ""
    orch._sessions.clear()
    orch._session_meta.clear()
    monkeypatch.setattr(orch.registry, "call", _success_result)

    response = client.post(
        "/chat",
        json={"session_id": "ttl-default-flow", "message": "\u770b\u770b\u7cfb\u7edf\u5185\u5b58\u60c5\u51b5"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["executed"] is True
    assert body["session_events"] == []
    assert body["tool_result"]["tool"] == "get_memory_status"


def test_audit_trace_contains_session_lifecycle(monkeypatch, tmp_path):
    orch = _make_orchestrator(monkeypatch, tmp_path)
    session_id = "ttl-trace"

    orch.run(session_id, "first")
    orch._session_meta[session_id]["last_seen"] -= config.SESSION_TTL_SECONDS + 1
    result = orch.run(session_id, "second")

    trace = orch.audit.trace(result["request_id"])
    stages = {event["stage"]: event for event in trace["trace"]["events"]}

    assert trace["found"] is True
    assert stages["session_lifecycle"]["events"] == ["session_expired", "session_reset"]
