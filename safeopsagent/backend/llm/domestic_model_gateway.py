"""Domestic model configuration and safe planning gateway.

The gateway selects a configured model service and delegates the actual
OpenAI-compatible HTTP request to the existing low-level provider. It never
executes tools and never exposes credentials through its public metadata.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping

import httpx

from backend import config
from backend.llm.mock_provider import MockProvider
from backend.llm.openai_compatible_provider import OpenAICompatibleProvider


DEFAULT_API_BASES = {
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "kimi": "https://api.moonshot.cn/v1",
}

VENDOR_LABELS = {
    "deepseek": "DeepSeek",
    "qwen": "千问",
    "kimi": "Kimi",
    "custom": "自定义模型服务",
    "offline_safe": "内置安全规划器",
}

PROVIDER_ALIASES = {
    "deepseek": "deepseek",
    "qwen": "qwen",
    "dashscope": "qwen",
    "kimi": "kimi",
    "moonshot": "kimi",
}

OFFLINE_ALIASES = {"", "mock", "offline", "offline_safe"}

VENDOR_KEY_NAMES = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
}

VENDOR_BASE_NAMES = {
    "deepseek": "DEEPSEEK_API_BASE",
    "qwen": "DASHSCOPE_API_BASE",
    "kimi": "MOONSHOT_API_BASE",
}

VENDOR_MODEL_NAMES = {
    "deepseek": ("DEEPSEEK_MODEL",),
    "qwen": ("DASHSCOPE_MODEL", "QWEN_MODEL"),
    "kimi": ("MOONSHOT_MODEL", "KIMI_MODEL"),
}

SAFE_FALLBACK_REASONS = {
    "offline_safe_configured",
    "provider_not_selected",
    "unsupported_model_provider",
    "ambiguous_vendor_keys",
    "missing_model_api_key",
    "missing_model_api_base",
    "missing_model_name",
    "model_api_timeout",
    "model_api_http_error",
    "model_api_error",
    "model_returned_non_json",
    "model_returned_invalid_schema",
}

FALLBACK_REASON_ALIASES = {
    "missing_openai_compatible_config": "missing_model_api_key",
}


@dataclass(frozen=True)
class ModelRuntimeConfig:
    """Resolved model settings with a redacted representation."""

    agent_mode: str
    model_provider: str
    model_vendor: str
    model_name: str
    planner_source: str
    api_base: str = ""
    api_key: str = field(default="", repr=False)
    fallback_reason: str = ""

    @property
    def model_api_enabled(self) -> bool:
        return self.agent_mode == "model_api"

    def public_metadata(self) -> dict[str, str]:
        return {
            "agent_mode": self.agent_mode,
            "model_provider": self.model_provider,
            "model_vendor": self.model_vendor,
            "model_name": self.model_name,
            "planner_source": self.planner_source,
        }


def resolve_model_config(environ: Mapping[str, str] | None = None) -> ModelRuntimeConfig:
    """Resolve new and legacy environment variables without guessing secrets."""

    env = os.environ if environ is None else environ
    new_provider = _value(env, "MODEL_PROVIDER").lower()
    legacy_provider = _value(env, "LLM_PROVIDER").lower()

    if new_provider:
        provider = PROVIDER_ALIASES.get(new_provider)
        if new_provider in OFFLINE_ALIASES:
            return _offline_config("offline_safe_configured")
        if provider is None:
            return _offline_config("unsupported_model_provider")
    elif legacy_provider:
        if legacy_provider in OFFLINE_ALIASES:
            return _offline_config("offline_safe_configured")
        if legacy_provider == "openai_compatible":
            provider = _infer_provider_from_base(
                _first(env, "MODEL_API_BASE", "LLM_API_BASE")
            ) or "custom"
        else:
            provider = PROVIDER_ALIASES.get(legacy_provider)
            if provider is None:
                return _offline_config("unsupported_model_provider")
    else:
        keyed_providers = [
            provider_name
            for provider_name, key_name in VENDOR_KEY_NAMES.items()
            if _value(env, key_name)
        ]
        if len(keyed_providers) > 1:
            return _offline_config("ambiguous_vendor_keys")
        if not keyed_providers:
            return _offline_config("provider_not_selected")
        provider = keyed_providers[0]

    api_key = _resolve_api_key(env, provider)
    api_base = _resolve_api_base(env, provider)
    model_name = _resolve_model_name(env, provider)

    if not api_key:
        return _offline_config("missing_model_api_key")
    if not api_base:
        return _offline_config("missing_model_api_base")
    if not model_name:
        return _offline_config("missing_model_name")

    return ModelRuntimeConfig(
        agent_mode="model_api",
        model_provider=provider,
        model_vendor=VENDOR_LABELS[provider],
        model_name=model_name,
        planner_source="domestic_model",
        api_base=api_base.rstrip("/"),
        api_key=api_key,
    )


class DomesticModelGateway:
    """Product-facing planner for domestic and compatible model services."""

    def __init__(
        self,
        settings: ModelRuntimeConfig | None = None,
        client: httpx.Client | None = None,
        fallback: MockProvider | None = None,
    ) -> None:
        self.settings = settings or resolve_model_config()
        self.fallback = fallback or MockProvider()
        self.transport = None
        if self.settings.model_api_enabled:
            self.transport = OpenAICompatibleProvider(
                api_base=self.settings.api_base,
                api_key=self.settings.api_key,
                model=self.settings.model_name,
                timeout=config.LLM_TIMEOUT_SECONDS,
                max_output_chars=config.LLM_MAX_OUTPUT_CHARS,
                client=client,
                fallback=self.fallback,
            )

    def public_metadata(self) -> dict[str, str]:
        return self.settings.public_metadata()

    def chat(self, messages: list[dict], tools: list[dict]) -> dict[str, Any]:
        if self.transport is None:
            return self.offline_result(
                messages,
                tools,
                self.settings.fallback_reason or "offline_safe_configured",
            )

        result = self.transport.chat(messages, tools)
        if result.get("agent_mode") == "offline_safe":
            return self._normalize_offline_result(
                result,
                _safe_fallback_reason(result.get("fallback_reason")),
            )
        return self._normalize_model_result(result)

    def summarize(self, text: str, max_chars: int = 500) -> str:
        if self.transport is None:
            return self.fallback.summarize(text, max_chars)
        return self.transport.summarize(text, max_chars)

    def offline_result(
        self,
        messages: list[dict],
        tools: list[dict],
        reason: str = "offline_safe_configured",
    ) -> dict[str, Any]:
        return self._normalize_offline_result(
            self.fallback.chat(messages, tools),
            _safe_fallback_reason(reason),
        )

    def _normalize_model_result(self, result: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(result)
        normalized.update(self.settings.public_metadata())
        normalized["planner_confidence"] = _safe_confidence(
            normalized.get("confidence", 0.0)
        )
        normalized["planner_explanation"] = str(
            normalized.get("explanation", normalized.get("reason", ""))
        )[:500]
        normalized.pop("fallback_reason", None)
        return normalized

    def _normalize_offline_result(
        self,
        result: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        normalized = dict(result)
        normalized.update(_offline_config(reason).public_metadata())
        normalized["planner_confidence"] = _safe_confidence(
            normalized.get("confidence", 0.0)
        )
        normalized["planner_explanation"] = str(
            normalized.get("explanation", normalized.get("reason", ""))
        )[:500]
        normalized["fallback_reason"] = reason
        return normalized


def _offline_config(reason: str) -> ModelRuntimeConfig:
    return ModelRuntimeConfig(
        agent_mode="offline_safe",
        model_provider="offline_safe",
        model_vendor=VENDOR_LABELS["offline_safe"],
        model_name="offline",
        planner_source="offline_safe",
        fallback_reason=_safe_fallback_reason(reason),
    )


def _resolve_api_key(env: Mapping[str, str], provider: str) -> str:
    names = ["MODEL_API_KEY"]
    if provider in VENDOR_KEY_NAMES:
        names.append(VENDOR_KEY_NAMES[provider])
    names.append("LLM_API_KEY")
    return _first(env, *names)


def _resolve_api_base(env: Mapping[str, str], provider: str) -> str:
    names = ["MODEL_API_BASE"]
    vendor_base = VENDOR_BASE_NAMES.get(provider)
    if vendor_base:
        names.append(vendor_base)
    names.append("LLM_API_BASE")
    configured = _first(env, *names)
    return configured or DEFAULT_API_BASES.get(provider, "")


def _resolve_model_name(env: Mapping[str, str], provider: str) -> str:
    names = ["MODEL_NAME"]
    names.extend(VENDOR_MODEL_NAMES.get(provider, ()))
    names.append("LLM_MODEL")
    return _first(env, *names)


def _infer_provider_from_base(api_base: str) -> str:
    lowered = (api_base or "").lower()
    if "deepseek" in lowered:
        return "deepseek"
    if "dashscope" in lowered or "aliyun" in lowered or "qwen" in lowered:
        return "qwen"
    if "moonshot" in lowered or "kimi" in lowered:
        return "kimi"
    return ""


def _safe_fallback_reason(value: Any) -> str:
    reason = FALLBACK_REASON_ALIASES.get(str(value or ""), str(value or ""))
    return reason if reason in SAFE_FALLBACK_REASONS else "model_api_error"


def _safe_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


def _first(env: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = _value(env, name)
        if value:
            return value
    return ""


def _value(env: Mapping[str, str], name: str) -> str:
    return str(env.get(name, "") or "").strip()
