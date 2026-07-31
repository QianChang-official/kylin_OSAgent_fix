from fastapi.testclient import TestClient

from backend.app import app
from backend.security.guardrail import Guardrail
from backend.tools.registry import ToolResult, get_registry

client = TestClient(app)


def test_safe_memory_tool_scores_low():
    guardrail = Guardrail()
    input_check = guardrail.check_input("\u770b\u770b\u7cfb\u7edf\u5185\u5b58\u60c5\u51b5")
    tool_check = guardrail.validate_tool_selection("get_memory_status", ["get_memory_status"])
    arg_check = guardrail.validate_tool_args("get_memory_status", {})

    result = guardrail.score_100(
        input_check=input_check,
        tool_check=tool_check,
        arg_check=arg_check,
        tool_name="get_memory_status",
        arguments={},
    )

    assert result.score < 41
    assert result.risk_level == "low"
    assert result.legacy_risk_level in {1, 2}
    assert result.security_decision == "allow"
    assert result.blocked is False


def test_dangerous_delete_input_scores_critical():
    guardrail = Guardrail()
    input_check = guardrail.check_input("\u5e2e\u6211 rm -rf /")

    result = guardrail.score_100(input_check=input_check)

    assert result.score == 100
    assert result.risk_level == "forbidden"
    assert result.legacy_risk_level == 5
    assert result.security_decision == "reject"
    assert result.blocked is True
    assert any("delete_command" in rule or "dangerous_cmd" in rule for rule in result.matched_rules)


def test_shell_injection_argument_scores_critical():
    guardrail = Guardrail()
    input_check = guardrail.check_input("service status")
    tool_check = guardrail.validate_tool_selection("get_service_status", ["get_service_status"])
    arg_check = guardrail.validate_tool_args("get_service_status", {"service_name": "nginx;rm"})

    result = guardrail.score_100(
        input_check=input_check,
        tool_check=tool_check,
        arg_check=arg_check,
        tool_name="get_service_status",
        arguments={"service_name": "nginx;rm"},
    )

    assert result.score == 100
    assert result.risk_level == "forbidden"
    assert result.legacy_risk_level == 5
    assert result.security_decision == "reject"
    assert result.blocked is True


def test_registered_but_unclassified_tool_fails_closed():
    guardrail = Guardrail()
    tool_check = guardrail.validate_tool_selection("new_external_tool", ["new_external_tool"])
    arg_check = guardrail.validate_tool_args("new_external_tool", {})

    result = guardrail.score_100(
        tool_check=tool_check,
        arg_check=arg_check,
        tool_name="new_external_tool",
        arguments={},
    )

    assert result.score == 100
    assert result.security_decision == "reject"
    assert result.blocked is True
    assert "unclassified_tool:new_external_tool" in result.matched_rules


def test_tools_call_returns_risk_score_fields(monkeypatch):
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
    assert isinstance(body["risk_score"], int)
    assert body["risk_score"] >= 0
    assert body["risk_level"] == "low"
    assert body["legacy_risk_level"] in {1, 2}
    assert body["security_decision"] == "allow"
    assert body["risk_band"] == "low"
    assert isinstance(body["risk_factors"], list)
    assert isinstance(body["matched_rules"], list)


def test_tools_call_high_risk_path_is_blocked_before_execution(monkeypatch):
    called = {"value": False}

    def fake_call(name, args):
        called["value"] = True
        return ToolResult(tool=name, status="success", data={})

    monkeypatch.setattr(get_registry(), "call", fake_call)

    response = client.post(
        "/tools/call",
        json={"tool_name": "large_file_scan", "arguments": {"path": "/etc", "min_size_mb": 1}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["risk_score"] >= 70
    assert body["risk_level"] in {"high", "forbidden"}
    assert body["security_decision"] in {"confirm", "reject"}
    assert body["security_reason"] in {"confirmation_required", "blocked_invalid_arguments"}
    assert called["value"] is False
