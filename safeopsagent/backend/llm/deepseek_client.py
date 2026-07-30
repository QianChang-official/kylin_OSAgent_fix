"""Backward-compatible LLM client facade for SafeOpsAgent."""
from __future__ import annotations

import os
from typing import Any, Dict, List

from backend import config
from backend.llm.domestic_model_gateway import (
    DomesticModelGateway,
    resolve_model_config,
)


class DeepSeekClient:
    """Compatibility facade that delegates planning to DomesticModelGateway."""

    def __init__(
        self,
        api_key: str | None = None,
        gateway: DomesticModelGateway | None = None,
    ) -> None:
        if gateway is None:
            env = dict(os.environ)
            if api_key is not None:
                env["DEEPSEEK_API_KEY"] = api_key
            gateway = DomesticModelGateway(settings=resolve_model_config(env))
        self.gateway = gateway
        self.mock = gateway.fallback
        self.openai_compatible = gateway.transport

        # Mutable compatibility attributes used by existing tests and callers.
        self.provider = gateway.settings.model_provider
        self.api_key = api_key if api_key is not None else gateway.settings.api_key

    def chat(
        self,
        messages: List[Dict],
        tools: List[Dict],
        require_json: bool = True,
    ) -> Dict[str, Any]:
        del require_json  # JSON planning is always enforced by the gateway.
        if self._use_mock():
            return self._offline_result(messages, tools)
        return self.gateway.chat(messages, tools)

    def summarize(self, text: str, max_chars: int = 500) -> str:
        if self._use_mock():
            return self.mock.summarize(text, max_chars)
        return self.gateway.summarize(text, max_chars)

    def public_metadata(self) -> dict[str, str]:
        if self._use_mock():
            return {
                "agent_mode": "offline_safe",
                "model_provider": "offline_safe",
                "model_vendor": "内置安全规划器",
                "model_name": "offline",
                "planner_source": "offline_safe",
            }
        return self.gateway.public_metadata()

    def _use_mock(self) -> bool:
        return self.provider in {"mock", "offline", "offline_safe", ""} or not self.api_key

    def _offline_result(
        self,
        messages: List[Dict],
        tools: List[Dict],
        fallback_reason: str = "offline_safe_configured",
    ) -> Dict[str, Any]:
        return self.gateway.offline_result(messages, tools, fallback_reason)

    def _fallback_no_api(self, tools: List[Dict]) -> Dict[str, Any]:
        del tools
        return {
            "tool": "none",
            "args": {},
            "reason": "API unavailable - offline safety planner active",
            "raw": "",
        }

    def rca_fallback_disk(self, path: str, size: str) -> str:
        return config.RCA_DISK_TEMPLATE.format(path=path, size=size)
