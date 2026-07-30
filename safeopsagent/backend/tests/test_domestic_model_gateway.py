import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.app import app
from backend.llm.domestic_model_gateway import (
    DomesticModelGateway,
    resolve_model_config,
)


SENTINEL = "unit-test-secret-never-expose"
TOOLS = [
    {
        "name": "get_memory_status",
        "description": "memory status",
        "inputSchema": {"type": "object", "properties": {}},
    }
]


def _model_payload(tool_name: str = "get_memory_status") -> dict:
    return {
        "intent": "memory_status_query",
        "tool_plan": [
            {
                "tool_name": tool_name,
                "arguments": {},
                "reason": "check memory",
            }
        ],
        "confidence": 0.91,
        "explanation": "Plan a safe read-only memory check.",
    }


@pytest.mark.parametrize(
    "provider,key_name,expected_url,vendor",
    [
        ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/chat/completions", "DeepSeek"),
        (
            "qwen",
            "DASHSCOPE_API_KEY",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "千问",
        ),
        ("kimi", "MOONSHOT_API_KEY", "https://api.moonshot.cn/v1/chat/completions", "Kimi"),
    ],
)
def test_vendor_request_url_auth_model_and_response(
    provider, key_name, expected_url, vendor
):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        content = json.dumps(_model_payload(), ensure_ascii=False)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    env = {
        "MODEL_PROVIDER": provider,
        key_name: SENTINEL,
        "MODEL_NAME": f"unit-{provider}-model",
    }
    settings = resolve_model_config(env)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = DomesticModelGateway(settings=settings, client=client).chat(
        [{"role": "user", "content": "check memory"}], TOOLS
    )

    assert captured["url"] == expected_url
    assert captured["authorization"] == f"Bearer {SENTINEL}"
    assert captured["payload"]["model"] == f"unit-{provider}-model"
    assert result["agent_mode"] == "model_api"
    assert result["model_provider"] == provider
    assert result["model_vendor"] == vendor
    assert result["planner_source"] == "domestic_model"
    assert result["tool_plan"][0]["tool_name"] == "get_memory_status"


def test_new_environment_variables_have_highest_priority():
    settings = resolve_model_config(
        {
            "MODEL_PROVIDER": "qwen",
            "MODEL_API_KEY": "new-key",
            "MODEL_API_BASE": "https://new.example/v1",
            "MODEL_NAME": "new-model",
            "DASHSCOPE_API_KEY": "vendor-key",
            "LLM_PROVIDER": "deepseek",
            "LLM_API_KEY": "legacy-key",
            "LLM_API_BASE": "https://legacy.example/v1",
            "LLM_MODEL": "legacy-model",
        }
    )

    assert settings.model_provider == "qwen"
    assert settings.api_key == "new-key"
    assert settings.api_base == "https://new.example/v1"
    assert settings.model_name == "new-model"


def test_legacy_openai_compatible_configuration_is_inferred_without_public_name():
    settings = resolve_model_config(
        {
            "LLM_PROVIDER": "openai_compatible",
            "LLM_API_KEY": "legacy-key",
            "LLM_API_BASE": "https://api.deepseek.com",
            "LLM_MODEL": "legacy-model",
        }
    )

    assert settings.model_provider == "deepseek"
    assert settings.model_vendor == "DeepSeek"
    assert "openai" not in json.dumps(settings.public_metadata()).lower()


def test_legacy_deepseek_provider_variables_remain_supported():
    settings = resolve_model_config(
        {
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "legacy-vendor-key",
            "DEEPSEEK_API_BASE": "https://legacy.deepseek.example",
            "DEEPSEEK_MODEL": "legacy-vendor-model",
        }
    )

    assert settings.agent_mode == "model_api"
    assert settings.model_provider == "deepseek"
    assert settings.model_vendor == "DeepSeek"
    assert settings.api_key == "legacy-vendor-key"
    assert settings.api_base == "https://legacy.deepseek.example"
    assert settings.model_name == "legacy-vendor-model"


def test_unknown_legacy_compatible_service_is_custom():
    settings = resolve_model_config(
        {
            "LLM_PROVIDER": "openai_compatible",
            "LLM_API_KEY": "legacy-key",
            "LLM_API_BASE": "https://model.example/v1",
            "LLM_MODEL": "custom-model",
        }
    )

    assert settings.model_provider == "custom"
    assert settings.model_vendor == "自定义模型服务"
    assert settings.planner_source == "domestic_model"


def test_single_vendor_key_is_inferred_but_multiple_keys_fall_back():
    inferred = resolve_model_config(
        {"DASHSCOPE_API_KEY": "one-key", "MODEL_NAME": "configured-model"}
    )
    ambiguous = resolve_model_config(
        {
            "DEEPSEEK_API_KEY": "one-key",
            "MOONSHOT_API_KEY": "two-key",
            "MODEL_NAME": "configured-model",
        }
    )

    assert inferred.model_provider == "qwen"
    assert ambiguous.model_provider == "offline_safe"
    assert ambiguous.fallback_reason == "ambiguous_vendor_keys"


def test_generic_key_without_provider_and_incomplete_explicit_config_fall_back():
    generic_only = resolve_model_config(
        {"MODEL_API_KEY": "generic-key", "MODEL_NAME": "configured-model"}
    )
    missing_key = resolve_model_config(
        {"MODEL_PROVIDER": "kimi", "MODEL_NAME": "configured-model"}
    )
    missing_model = resolve_model_config(
        {"MODEL_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "vendor-key"}
    )

    assert generic_only.fallback_reason == "provider_not_selected"
    assert missing_key.fallback_reason == "missing_model_api_key"
    assert missing_model.fallback_reason == "missing_model_name"
    assert {generic_only.agent_mode, missing_key.agent_mode, missing_model.agent_mode} == {
        "offline_safe"
    }


@pytest.mark.parametrize(
    "response_kind,expected_reason",
    [
        ("timeout", "model_api_timeout"),
        ("http_error", "model_api_http_error"),
        ("non_json", "model_returned_non_json"),
        ("invalid_schema", "model_returned_invalid_schema"),
    ],
)
def test_provider_failures_use_safe_offline_metadata_without_secret(
    response_kind, expected_reason, caplog
):
    def handler(request: httpx.Request) -> httpx.Response:
        if response_kind == "timeout":
            raise httpx.ReadTimeout(SENTINEL, request=request)
        if response_kind == "http_error":
            return httpx.Response(500, text=SENTINEL)
        if response_kind == "non_json":
            content = f"not-json-{SENTINEL}"
        else:
            content = json.dumps({"intent": "bad", "tool_plan": "invalid"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    settings = resolve_model_config(
        {
            "MODEL_PROVIDER": "deepseek",
            "MODEL_API_KEY": SENTINEL,
            "MODEL_NAME": "unit-model",
        }
    )
    gateway = DomesticModelGateway(
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = gateway.chat([{"role": "user", "content": "check memory"}], TOOLS)
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["agent_mode"] == "offline_safe"
    assert result["model_provider"] == "offline_safe"
    assert result["model_vendor"] == "内置安全规划器"
    assert result["planner_source"] == "offline_safe"
    assert result["fallback_reason"] == expected_reason
    assert SENTINEL not in repr(settings)
    assert SENTINEL not in serialized
    assert SENTINEL not in caplog.text


def test_unknown_model_tool_remains_non_executable_plan():
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(_model_payload("delete_everything"))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    settings = resolve_model_config(
        {
            "MODEL_PROVIDER": "deepseek",
            "MODEL_API_KEY": "unit-key",
            "MODEL_NAME": "unit-model",
        }
    )
    result = DomesticModelGateway(
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).chat([{"role": "user", "content": "do something"}], TOOLS)

    assert result["tool"] == "none"
    assert result["tool_plan"][0]["tool_name"] == "delete_everything"
    assert result["planner_source"] == "domestic_model"


def test_secret_never_appears_in_status_chat_trace_or_exception(monkeypatch, caplog):
    monkeypatch.setenv("MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("MODEL_API_KEY", SENTINEL)
    monkeypatch.setenv("MODEL_NAME", "unit-model")
    monkeypatch.setattr(app_module, "_orchestrator", None)
    client = TestClient(app)

    status = client.get("/agent/status")
    blocked = client.post(
        "/chat",
        json={"session_id": "secret-sentinel", "message": "rm -rf /"},
    )
    trace = client.get(f"/audit/trace/{blocked.json()['request_id']}")
    combined = status.text + blocked.text + trace.text + caplog.text

    assert status.status_code == 200
    assert status.json()["agent_mode"] == "model_api"
    assert status.json()["model_provider"] == "deepseek"
    assert status.json()["model_vendor"] == "DeepSeek"
    assert status.json()["model_name"] == "unit-model"
    assert status.json()["planner_source"] == "domestic_model"
    assert blocked.status_code == 200
    assert trace.status_code == 200
    assert SENTINEL not in combined
    assert blocked.json()["security_decision"] == "reject"
    assert blocked.json()["executed"] is False
