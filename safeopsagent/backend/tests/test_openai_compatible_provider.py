import json

import httpx

from backend.llm.openai_compatible_provider import OpenAICompatibleProvider

TOOLS = [
    {
        "name": "get_memory_status",
        "description": "memory status",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_port_usage",
        "description": "port usage",
        "inputSchema": {
            "type": "object",
            "properties": {"port": {"type": "integer", "minimum": 1, "maximum": 65535}},
        },
    },
]


class FakeResponse:
    def __init__(self, content: str):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


class FakeClient:
    def __init__(self, content: str | None = None, exc: Exception | None = None):
        self.content = content
        self.exc = exc
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "json": json, "timeout": timeout})
        if self.exc:
            raise self.exc
        return FakeResponse(self.content or "{}")


def _provider(content: str | None = None, exc: Exception | None = None) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_base="https://api.example.com/v1",
        api_key="unit-test-key",
        model="test-model",
        timeout=3,
        client=FakeClient(content=content, exc=exc),
    )


def test_openai_compatible_provider_parses_valid_model_json():
    content = json.dumps(
        {
            "intent": "system_resource_check",
            "tool_plan": [
                {
                    "tool_name": "get_memory_status",
                    "arguments": {},
                    "reason": "User asked to inspect memory status.",
                }
            ],
            "confidence": 0.86,
            "explanation": "Plan a safe read-only memory inspection.",
        }
    )
    provider = _provider(content)

    result = provider.chat([{"role": "user", "content": "check memory"}], TOOLS)

    assert result["tool"] == "get_memory_status"
    assert result["args"] == {}
    assert result["intent"] == "system_resource_check"
    assert result["confidence"] == 0.86
    assert result["planner_source"] == "openai_compatible"
    assert result["agent_mode"] == "model_api"
    assert result["model_name"] == "test-model"


def test_openai_compatible_provider_non_json_falls_back_without_crashing():
    provider = _provider("not json")

    result = provider.chat([{"role": "user", "content": "check memory"}], TOOLS)

    assert result["planner_source"] == "offline_safe"
    assert result["agent_mode"] == "offline_safe"
    assert result["fallback_reason"] == "model_returned_non_json"


def test_openai_compatible_provider_missing_api_key_falls_back():
    provider = OpenAICompatibleProvider(
        api_base="https://api.example.com/v1",
        api_key="",
        model="test-model",
        client=FakeClient("{}"),
    )

    result = provider.chat([{"role": "user", "content": "check memory"}], TOOLS)

    assert result["planner_source"] == "offline_safe"
    assert result["fallback_reason"] == "missing_openai_compatible_config"


def test_openai_compatible_provider_timeout_falls_back_without_key_leak():
    provider = _provider(exc=httpx.TimeoutException("unit-test-key timeout"))

    result = provider.chat([{"role": "user", "content": "check memory"}], TOOLS)
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["planner_source"] == "offline_safe"
    assert result["fallback_reason"] == "model_api_timeout"
    assert "unit-test-key" not in serialized


def test_openai_compatible_provider_unknown_tool_is_not_executable():
    content = json.dumps(
        {
            "intent": "unsafe_plan",
            "tool_plan": [
                {
                    "tool_name": "delete_everything",
                    "arguments": {"path": "/"},
                    "reason": "This tool is not in the registry.",
                }
            ],
            "confidence": 0.99,
            "explanation": "Invalid tool should be rejected by provider normalization.",
        }
    )
    provider = _provider(content)

    result = provider.chat([{"role": "user", "content": "do unsafe thing"}], TOOLS)

    assert result["tool"] == "none"
    assert result["args"] == {}
    assert result["planner_source"] == "openai_compatible"
    assert result["tool_plan"][0]["tool_name"] == "delete_everything"


def test_openai_compatible_provider_endpoint_and_payload_are_openai_compatible():
    content = json.dumps(
        {
            "intent": "port_check",
            "tool_plan": [
                {
                    "tool_name": "get_port_usage",
                    "arguments": {"port": 22},
                    "reason": "Check SSH listener.",
                }
            ],
            "confidence": 0.8,
            "explanation": "Use read-only port inspection.",
        }
    )
    fake_client = FakeClient(content=content)
    provider = OpenAICompatibleProvider(
        api_base="https://api.example.com/compatible-mode/v1",
        api_key="unit-test-key",
        model="qwen-test",
        timeout=7,
        client=fake_client,
    )

    result = provider.chat([{"role": "user", "content": "check port 22"}], TOOLS)

    assert result["tool"] == "get_port_usage"
    assert fake_client.calls[0]["url"] == "https://api.example.com/compatible-mode/v1/chat/completions"
    assert fake_client.calls[0]["headers"]["Authorization"] == "Bearer unit-test-key"
    assert fake_client.calls[0]["json"]["model"] == "qwen-test"
    assert fake_client.calls[0]["json"]["response_format"] == {"type": "json_object"}
    assert fake_client.calls[0]["timeout"] == 7
