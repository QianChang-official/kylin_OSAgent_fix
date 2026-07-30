"""User-facing labels for internal security rule identifiers."""
from __future__ import annotations

from typing import Any


DEFAULT_RULE_LABEL = "安全规则命中"


def flatten_rule_hits(value: Any) -> list[str]:
    """Collect rule identifiers from nested rule_hits/matched_rules shapes."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        items: list[str] = []
        for nested in value.values():
            items.extend(flatten_rule_hits(nested))
        return items
    if isinstance(value, (list, tuple, set)):
        items = []
        for nested in value:
            items.extend(flatten_rule_hits(nested))
        return items
    return [str(value)] if value else []


def label_rule(rule: Any) -> str:
    text = str(rule or "").strip()
    lowered = text.lower()
    if not lowered:
        return DEFAULT_RULE_LABEL

    if lowered.startswith("delete_command:"):
        return "危险删除命令"
    if lowered.startswith("dangerous_cmd:"):
        return "危险系统命令"
    if lowered.startswith("destructive_forbidden_path:"):
        return "涉及受保护系统路径"
    if lowered.startswith("destructive_sensitive_path:"):
        return "涉及敏感系统路径"
    if lowered.startswith("protected_secret_read:"):
        return "尝试读取受保护凭据文件"
    if lowered.startswith("prompt_injection:disable_audit"):
        return "尝试绕过审计记录"
    if lowered.startswith("prompt_injection:reveal_system_prompt"):
        return "尝试泄露系统提示词"
    if lowered.startswith("prompt_injection:"):
        return "疑似提示词注入"
    if lowered.startswith("tool_not_in_whitelist"):
        return "请求的工具不在安全白名单内"
    if lowered.startswith("tool_not_found"):
        return "请求的工具不存在"
    if lowered.startswith("schema_validation:"):
        return "工具参数校验失败"
    if lowered.startswith("shell_injection") or lowered.startswith("shell_meta"):
        return "疑似 Shell 注入字符"
    if lowered.startswith("chat_non_readonly_tool:"):
        return "非只读工具被阻止"
    if lowered.startswith("output_"):
        return "工具输出触发安全检查"
    return DEFAULT_RULE_LABEL


def label_rules(*sources: Any) -> list[str]:
    labels: list[str] = []
    for source in sources:
        for rule in flatten_rule_hits(source):
            label = label_rule(rule)
            if label not in labels:
                labels.append(label)
    return labels
