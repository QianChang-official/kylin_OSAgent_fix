from fastapi.testclient import TestClient

from backend import app as app_module
from backend.app import app
from backend.tools.registry import ToolResult, get_registry


client = TestClient(app)


def test_tools_list_still_works():
    response = client.get("/tools/list")

    assert response.status_code == 200
    tool_names = {tool["name"] for tool in response.json()["tools"]}
    assert "get_memory_status" in tool_names
    assert "get_port_usage" in tool_names
    assert "get_service_status" in tool_names


def test_tools_call_memory_status(monkeypatch):
    monkeypatch.setattr(
        get_registry(),
        "call",
        lambda name, args: ToolResult(
            tool=name,
            status="success",
            data={"total_mb": 16000, "used_mb": 8000},
            raw_output="Mem: 16000 8000",
        ),
    )

    response = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["tool_name"] == "get_memory_status"
    assert body["result"]["data"]["total_mb"] == 16000
    assert body["security_decision"] == "allow"
    assert body["security_reason"] == "executed"


def test_tools_call_port_usage(monkeypatch):
    monkeypatch.setattr(
        get_registry(),
        "call",
        lambda name, args: ToolResult(
            tool=name,
            status="success",
            data={"port": args["port"], "listeners": [{"pid": "1234", "process": "python"}]},
        ),
    )

    response = client.post("/tools/call", json={"tool_name": "get_port_usage", "arguments": {"port": 8080}})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["result"]["data"]["listeners"][0]["process"] == "python"


def test_tools_call_service_missing_does_not_crash(monkeypatch):
    monkeypatch.setattr(
        get_registry(),
        "call",
        lambda name, args: ToolResult(
            tool=name,
            status="command_failed",
            data={"service_name": args["service_name"], "active_state": "inactive"},
            raw_output="Unit nginx.service could not be found.",
            error="unit not found",
        ),
    )

    response = client.post(
        "/tools/call",
        json={"tool_name": "get_service_status", "arguments": {"service_name": "nginx"}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["result"]["data"]["service_name"] == "nginx"
    assert body["error"] == "unit not found"


def test_tools_call_unknown_tool_returns_structured_error():
    response = client.post("/tools/call", json={"tool_name": "not_a_tool", "arguments": {}})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "blocked_tool_not_found"
    assert "not found" in body["error"]


def test_tools_call_rejects_invalid_arguments():
    response = client.post(
        "/tools/call",
        json={"tool_name": "get_port_usage", "arguments": {"port": "8080; rm -rf /"}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "blocked_invalid_arguments"


def test_tools_call_rejects_journal_lines_out_of_range(monkeypatch):
    called = {"value": False}
    monkeypatch.setattr(get_registry(), "call", lambda name, args: called.update(value=True))

    for lines in [0, 501]:
        response = client.post(
            "/tools/call",
            json={"tool_name": "journal_query", "arguments": {"lines": lines}},
        )
        body = response.json()

        assert response.status_code == 200
        assert body["success"] is False
        assert body["security_decision"] == "reject"
        assert body["security_reason"] == "blocked_invalid_arguments"
    assert called["value"] is False


def test_tools_call_accepts_valid_journal_args(monkeypatch):
    monkeypatch.setattr(
        get_registry(),
        "call",
        lambda name, args: ToolResult(
            tool=name,
            status="success",
            data=[{"line": 1, "content": "ok"}],
            raw_output="ok",
        ),
    )

    response = client.post(
        "/tools/call",
        json={"tool_name": "journal_query", "arguments": {"lines": 50, "service": "sshd.service"}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["security_decision"] == "allow"


def test_tools_call_rejects_service_name_shell_payload(monkeypatch):
    called = {"value": False}
    monkeypatch.setattr(get_registry(), "call", lambda name, args: called.update(value=True))

    response = client.post(
        "/tools/call",
        json={"tool_name": "get_service_status", "arguments": {"service_name": "nginx; rm -rf /"}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "blocked_invalid_arguments"
    assert called["value"] is False


def test_tools_call_guardrail_blocks_before_execution(monkeypatch):
    called = {"value": False}

    def fake_call(name, args):
        called["value"] = True
        return ToolResult(tool=name, status="success", data={})

    monkeypatch.setattr(get_registry(), "call", fake_call)

    response = client.post(
        "/tools/call",
        json={"tool_name": "large_file_scan", "arguments": {"path": "/etc/passwd", "size": "+1K"}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "blocked_by_guardrail"
    assert called["value"] is False


def test_tools_call_tool_exception_is_structured(monkeypatch):
    def boom(name, args):
        raise RuntimeError("tool exploded")

    monkeypatch.setattr(get_registry(), "call", boom)

    response = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "tool_exception"
    assert body["error"] == "tool exploded"


def test_tools_call_output_guardrail_blocks(monkeypatch):
    monkeypatch.setattr(
        get_registry(),
        "call",
        lambda name, args: ToolResult(
            tool=name,
            status="success",
            data={},
            raw_output="rm -rf /",
        ),
    )

    response = client.post("/tools/call", json={"tool_name": "get_memory_status", "arguments": {}})
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["security_decision"] == "reject"
    assert body["security_reason"] == "blocked_tool_output"
    assert body["rule_hits"]["tool_output"]
