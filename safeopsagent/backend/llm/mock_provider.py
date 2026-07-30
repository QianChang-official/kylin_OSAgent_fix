"""Deterministic mock LLM provider for stable demos without API access."""
import re
from typing import Any

from backend.llm.base import ToolSuggestion


SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "mkfs",
    "dd if=",
    "chmod 777",
    "\u5220\u9664\u6839\u76ee\u5f55",
    "\u683c\u5f0f\u5316",
]

PORT_KEYWORDS = ["\u7aef\u53e3", "\u5360\u7528", "\u76d1\u542c"]
MEMORY_KEYWORDS = ["\u5185\u5b58"]
SERVICE_KEYWORDS = ["\u670d\u52a1", "\u72b6\u6001"]
DISK_KEYWORDS = ["\u78c1\u76d8", "\u7a7a\u95f4", "\u786c\u76d8"]
PROCESS_KEYWORDS = ["\u8fdb\u7a0b"]
LOG_KEYWORDS = ["\u65e5\u5fd7", "\u9519\u8bef\u65e5\u5fd7", "\u6700\u8fd1\u65e5\u5fd7"]
NETWORK_KEYWORDS = ["\u7f51\u7edc", "\u8fde\u63a5", "\u76d1\u542c\u7aef\u53e3"]
CPU_KEYWORDS = ["CPU", "\u5904\u7406\u5668", "\u7cfb\u7edf\u8d1f\u8f7d", "load average"]
CLEANUP_KEYWORDS = ["\u5b89\u5168\u6e05\u7406", "\u6e05\u7406\u8ba1\u5212", "\u4e34\u65f6\u6587\u4ef6"]
LARGE_FILE_KEYWORDS = ["\u5927\u6587\u4ef6", "\u8d85\u5927\u6587\u4ef6", "\u5927\u6587\u4ef6\u626b\u63cf"]
SYSTEM_HEALTH_KEYWORDS = [
    "\u5361", "\u5361\u987f", "\u6162", "\u8d44\u6e90", "\u8d1f\u8f7d", "\u6027\u80fd",
    "\u5f02\u5e38", "\u6545\u969c", "\u5e2e\u6211\u770b\u770b",
    "\u7cfb\u7edf\u8fd0\u884c\u60c5\u51b5", "\u7cfb\u7edf\u72b6\u6001",
    "\u7cfb\u7edf\u5065\u5eb7", "\u6574\u4f53\u8fd0\u884c\u60c5\u51b5",
]


class MockProvider:
    """Rule-based tool suggestion provider.

    It only suggests tool calls. It never executes tools and never bypasses
    Guardrail, Tool Registry, SafeExecutor, or AuditLogger.
    """

    def suggest(self, text: str, tools: list[dict] | None = None) -> ToolSuggestion:
        normalized = (text or "").strip()
        lowered = normalized.lower()
        available = {tool.get("name") for tool in (tools or [])}

        if self._contains_dangerous_intent(lowered, normalized):
            return ToolSuggestion(
                tool_name="dangerous_intent",
                arguments={},
                intent="dangerous_intent",
                confidence=0.98,
                reason="Detected destructive or high-risk operation request.",
            )

        if self._matches(lowered, normalized, PORT_KEYWORDS) or any(
            word in lowered for word in ["port", "listen"]
        ):
            port = self._extract_port(normalized)
            if port and self._tool_available("get_port_usage", available):
                return ToolSuggestion(
                    tool_name="get_port_usage",
                    arguments={"port": port},
                    intent="port_usage_query",
                    confidence=0.9,
                    reason="Detected port/listener troubleshooting request.",
                )

        if any(word in lowered for word in ["memory", "ram"]) or self._matches(
            lowered, normalized, MEMORY_KEYWORDS
        ):
            if self._tool_available("get_memory_status", available):
                return ToolSuggestion(
                    tool_name="get_memory_status",
                    arguments={},
                    intent="memory_status_query",
                    confidence=0.9,
                    reason="Detected memory status request.",
                )

        if (
            self._matches(lowered, normalized, SYSTEM_HEALTH_KEYWORDS) or any(
            word in lowered for word in ["slow", "lag", "stuck", "performance", "resource", "load"]
            )
        ) and not self._is_cpu_request(normalized):
            if self._tool_available("get_memory_status", available):
                return ToolSuggestion(
                    tool_name="get_memory_status",
                    arguments={},
                    intent="system_resource_check",
                    confidence=0.78,
                    reason="Detected broad system performance troubleshooting request.",
                )

        if self._is_cpu_request(normalized):
            if self._tool_available("get_cpu_status", available):
                return ToolSuggestion(
                    tool_name="get_cpu_status",
                    arguments={},
                    intent="cpu_status_query",
                    confidence=0.9,
                    reason="Detected CPU usage or system-load request.",
                )

        if self._matches(lowered, normalized, CLEANUP_KEYWORDS) or any(
            phrase in lowered for phrase in ["safe cleanup", "cleanup plan", "temporary files"]
        ):
            if self._tool_available("safe_cleanup_plan", available):
                return ToolSuggestion(
                    tool_name="safe_cleanup_plan",
                    arguments={"path": "/tmp", "min_age_hours": 24, "max_files": 20},
                    intent="safe_cleanup_plan",
                    confidence=0.86,
                    reason="Detected a request for a reversible temporary-file cleanup plan.",
                )

        if self._matches(lowered, normalized, LARGE_FILE_KEYWORDS) or any(
            phrase in lowered for phrase in ["large file", "big file"]
        ):
            if self._tool_available("large_file_scan", available):
                return ToolSuggestion(
                    tool_name="large_file_scan",
                    arguments={"path": "/var/log", "size": "+100M"},
                    intent="large_file_query",
                    confidence=0.84,
                    reason="Detected a read-only large-file scan request.",
                )

        if self._matches(lowered, normalized, SERVICE_KEYWORDS) or any(
            word in lowered for word in ["systemctl", "service"]
        ):
            service_name = self._extract_service_name(normalized)
            if service_name and self._tool_available("get_service_status", available):
                return ToolSuggestion(
                    tool_name="get_service_status",
                    arguments={"service_name": service_name},
                    intent="service_status_query",
                    confidence=0.86,
                    reason="Detected systemd service status request.",
                )

        if any(word in lowered for word in ["df", "disk"]) or self._matches(
            lowered, normalized, DISK_KEYWORDS
        ):
            if self._tool_available("disk_usage", available):
                return ToolSuggestion(
                    tool_name="disk_usage",
                    arguments={},
                    intent="disk_usage_query",
                    confidence=0.84,
                    reason="Detected disk capacity request.",
                )

        if any(word in lowered for word in ["process", "cpu"]) or self._matches(
            lowered, normalized, PROCESS_KEYWORDS
        ):
            if self._tool_available("process_list", available):
                return ToolSuggestion(
                    tool_name="process_list",
                    arguments={},
                    intent="process_query",
                    confidence=0.83,
                    reason="Detected process or CPU inspection request.",
                )

        if any(word in lowered for word in ["journalctl", "log"]) or self._matches(
            lowered, normalized, LOG_KEYWORDS
        ):
            if self._tool_available("journal_query", available):
                return ToolSuggestion(
                    tool_name="journal_query",
                    arguments={"lines": 100 if "100" in normalized else 50, "service": ""},
                    intent="log_query",
                    confidence=0.82,
                    reason="Detected recent log inspection request.",
                )

        if any(word in lowered for word in ["netstat", "ss", "network"]) or self._matches(
            lowered, normalized, NETWORK_KEYWORDS
        ):
            if self._tool_available("network_status", available):
                return ToolSuggestion(
                    tool_name="network_status",
                    arguments={},
                    intent="network_status_query",
                    confidence=0.82,
                    reason="Detected network/listener status request.",
                )

        return ToolSuggestion(
            tool_name="none",
            arguments={},
            intent="unknown",
            confidence=0.2,
            reason="No deterministic mock rule matched the request.",
        )

    def chat(self, messages: list[dict], tools: list[dict]) -> dict[str, Any]:
        text = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                text = message.get("content", "")
                break

        available = {tool.get("name") for tool in (tools or [])}
        if self._is_broad_health_request(text):
            plan = []
            for name, reason in [
                ("get_memory_status", "Check memory pressure and available capacity."),
                ("get_cpu_status", "Check CPU usage and load average."),
                ("disk_usage", "Check filesystem capacity and high-usage mount points."),
            ]:
                if self._tool_available(name, available):
                    plan.append({"tool_name": name, "arguments": {}, "reason": reason})
            return {
                "tool": plan[0]["tool_name"] if plan else "none",
                "args": {},
                "reason": "Detected broad system health troubleshooting request.",
                "intent": "system_resource_check",
                "confidence": 0.88,
                "tool_name": plan[0]["tool_name"] if plan else "none",
                "arguments": {},
                "tool_plan": plan[:3],
                "explanation": "Use multiple read-only metrics to avoid a single-signal diagnosis.",
            }

        suggestion = self.suggest(text, tools)
        tool_plan = []
        if suggestion.tool_name not in {"none", "dangerous_intent"}:
            tool_plan.append({
                "tool_name": suggestion.tool_name,
                "arguments": suggestion.arguments,
                "reason": suggestion.reason,
            })
        return {
            "tool": suggestion.tool_name if suggestion.tool_name != "dangerous_intent" else "none",
            "args": suggestion.arguments,
            "reason": suggestion.reason,
            "raw": suggestion.as_dict(),
            "intent": suggestion.intent,
            "confidence": suggestion.confidence,
            "tool_name": suggestion.tool_name,
            "arguments": suggestion.arguments,
            "tool_plan": tool_plan,
            "explanation": suggestion.reason,
        }

    def summarize(self, text: str, max_chars: int = 500) -> str:
        return text[:max_chars]

    def _contains_dangerous_intent(self, lowered: str, original: str) -> bool:
        return any(pattern in lowered or pattern in original for pattern in DANGEROUS_PATTERNS)

    def _matches(self, lowered: str, original: str, keywords: list[str]) -> bool:
        return any(keyword.lower() in lowered or keyword in original for keyword in keywords)

    def _tool_available(self, name: str, available: set[str]) -> bool:
        return not available or name in available

    def _extract_port(self, text: str) -> int | None:
        for match in re.finditer(r"\b([1-9][0-9]{0,4})\b", text):
            port = int(match.group(1))
            if 1 <= port <= 65535:
                return port
        return None

    def _extract_service_name(self, text: str) -> str | None:
        lowered = text.lower()
        known_services = ["nginx", "sshd", "ssh", "mysql", "mariadb", "postgresql", "redis", "docker"]
        for service in known_services:
            if service in lowered and SERVICE_NAME_RE.fullmatch(service):
                return service

        for token in re.findall(r"[A-Za-z0-9_.@-]{1,64}", text):
            lowered_token = token.lower()
            if lowered_token in {"systemctl", "service", "status", "active"}:
                continue
            if SERVICE_NAME_RE.fullmatch(token):
                return token
        return None

    def _is_broad_health_request(self, text: str) -> bool:
        lowered = (text or "").lower()
        return not self._is_cpu_request(text) and (
            self._matches(lowered, text, SYSTEM_HEALTH_KEYWORDS) or any(
            phrase in lowered
            for phrase in ["system health", "system status", "system is slow", "resource check"]
            )
        )

    def _is_cpu_request(self, text: str) -> bool:
        lowered = (text or "").lower()
        return self._matches(lowered, text, CPU_KEYWORDS) or any(
            phrase in lowered for phrase in ["cpu", "load average", "system load"]
        )
