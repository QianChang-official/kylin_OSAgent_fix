"""Shared LLM provider result structures."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSuggestion:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    intent: str = "unknown"
    confidence: float = 0.0
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "intent": self.intent,
            "confidence": self.confidence,
            "reason": self.reason,
        }

