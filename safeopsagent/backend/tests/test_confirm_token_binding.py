"""确认令牌绑定的是服务端记下的操作，调用方改不了。

中风险工具走 dry-run 加一次性令牌确认。这条路径的关键性质是：**用户看到并
批准的那个操作，就是最终执行的那个操作**。如果调用方能在确认时替换工具名或
参数，整个确认流程就只是一道多余的往返。

当前实现让这件事在结构上不可能：ToolConfirmRequest 只有 confirmation_token
与 session_id，工具名与参数从服务端存的记录里取。这些测试把该性质钉住——
以后有人"顺手"让端点从请求体读参数，会立刻变红。
"""
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.app import ToolConfirmRequest, app
from backend.security.guardrail import Guardrail
from backend.security.risk_score import RiskScoreResult
from backend.tools.registry import ToolResult, get_registry

client = TestClient(app)

PLANNED_TOOL = "get_memory_status"
PLANNED_ARGS = {}


@pytest.fixture(autouse=True)
def clear_confirmations():
    app_module._confirmations.clear()
    yield
    app_module._confirmations.clear()


def _force_confirm(monkeypatch):
    monkeypatch.setattr(Guardrail, "score_100", lambda self, **kwargs: RiskScoreResult(
        score=70, risk_level="high", legacy_risk_level=4,
        security_decision="confirm", confirmation_required=True, blocked=False,
        matched_rules=["binding_test_rule"], factors=["binding_test_factor"],
    ))


def _make_token(monkeypatch, session="s1", args=None) -> str:
    if args is None:
        args = PLANNED_ARGS
    _force_confirm(monkeypatch)
    monkeypatch.setattr(get_registry(), "call", lambda n, a: ToolResult(
        tool=n, status="success", data={}, raw_output="ok"))
    resp = client.post("/tools/call", json={
        "session_id": session, "tool_name": PLANNED_TOOL, "arguments": args})
    token = resp.json().get("confirmation_token")
    assert token, f"未拿到确认令牌: {resp.json()}"
    return token


def test_confirm_request_cannot_carry_a_tool_or_arguments():
    """请求模型本身就没有可供替换的字段。

    这是比"校验参数指纹"更强的保证：无法表达的东西不需要校验。
    """
    fields = set(ToolConfirmRequest.model_fields)
    assert fields == {"confirmation_token", "session_id"}, (
        f"确认请求多出了字段 {fields - {'confirmation_token', 'session_id'}}；"
        "任何让调用方影响执行内容的字段都会破坏确认流程的意义"
    )


def test_extra_fields_in_the_confirm_body_are_ignored(monkeypatch):
    """把 tool_name/arguments 塞进请求体，不该有任何影响。"""
    executed: dict = {}

    def fake_call(name, args):
        executed["tool"] = name
        executed["args"] = dict(args or {})
        return ToolResult(tool=name, status="success", data={"ok": True}, raw_output="ok")

    token = _make_token(monkeypatch)
    monkeypatch.setattr(get_registry(), "call", fake_call)

    response = client.post("/tools/confirm", json={
        "confirmation_token": token,
        "session_id": "s1",
        "tool_name": "large_file_scan",      # 攻击者试图替换的内容
        "arguments": {"path": "/etc"},
    })

    assert response.status_code == 200
    assert executed.get("tool") == PLANNED_TOOL, "执行的工具被请求体改掉了"
    assert executed.get("args") == PLANNED_ARGS, "执行的参数被请求体改掉了"


def test_confirm_executes_exactly_what_was_planned(monkeypatch):
    """执行内容必须与创建令牌时记下的完全一致。"""
    executed: dict = {}

    def fake_call(name, args):
        executed["tool"] = name
        executed["args"] = dict(args or {})
        return ToolResult(tool=name, status="success", data={"ok": True}, raw_output="ok")

    token = _make_token(monkeypatch)
    monkeypatch.setattr(get_registry(), "call", fake_call)
    client.post("/tools/confirm", json={"confirmation_token": token, "session_id": "s1"})

    assert executed == {"tool": PLANNED_TOOL, "args": PLANNED_ARGS}


def test_each_token_stores_its_own_arguments(monkeypatch):
    """两次规划产生两个独立的令牌记录，互不覆盖。

    每个 UUID 对应一条独立的服务端记录。验证第一次规划的令牌记录在第二次
    规划后仍保存着第一次的原始数据——这是令牌绑定属性的直接证明，不依赖
    /tools/confirm 的执行路径细节。
    """
    token_first = _make_token(monkeypatch, session="s1")
    # 第二次规划用不同 session，确保 cleanup 不把 token_first 清掉
    token_second = _make_token(monkeypatch, session="s2")

    assert token_first != token_second, "两次规划应产生不同的令牌 UUID"

    record1 = app_module._confirmations.get(token_first)
    record2 = app_module._confirmations.get(token_second)
    assert record1 is not None, "第一个令牌的服务端记录丢失"
    assert record2 is not None, "第二个令牌的服务端记录丢失"
    assert record1["tool_name"] == PLANNED_TOOL
    assert record1["arguments"] == PLANNED_ARGS
    # 两条记录互相独立
    assert record1["original_request_id"] != record2["original_request_id"]
