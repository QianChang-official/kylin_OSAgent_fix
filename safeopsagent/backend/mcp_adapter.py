"""Pure-Python MCP adapter for SafeOpsAgent tools.

This module intentionally does not import the optional MCP SDK. It maps MCP
tool calls onto the existing HTTP handler functions so the MCP entry point
reuses Guardrail, RiskScorer, Tool Registry, SafeExecutor, and Audit Trace.
"""
from __future__ import annotations

from typing import Any

import backend.app as app_module
from backend.tools.registry import get_registry


CONFIRM_TOOL_NAME = "safeops_confirm_tool"
DEFAULT_MCP_SESSION_ID = "mcp"


def list_mcp_tools(include_confirm_tool: bool = True) -> list[dict[str, Any]]:
    """Return MCP-compatible tool definitions from the existing registry."""
    tools = [dict(tool) for tool in get_registry().list_tools()]
    if include_confirm_tool:
        tools.append(_confirm_tool_schema())
    return tools


def call_mcp_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a tool through the existing SafeOpsAgent security chain.

    Normal MCP tools are routed to ``/tools/call``'s handler. The special
    ``safeops_confirm_tool`` is routed to ``/tools/confirm``. This keeps MCP as
    a protocol adapter only; actual execution still happens in the existing
    audited path.
    """
    args = _copy_arguments(arguments)
    if name == CONFIRM_TOOL_NAME:
        return _call_confirm_tool(args)

    tool_args, session_id = _extract_session_id(args)
    request = app_module.ToolCallRequest(
        tool_name=name,
        arguments=tool_args,
        session_id=session_id,
    )
    return app_module.call_tool(request)


def _call_confirm_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    token = arguments.get("confirmation_token")
    if not isinstance(token, str) or not token.strip():
        return {
            "success": False,
            "tool_name": CONFIRM_TOOL_NAME,
            "security_decision": "reject",
            "security_reason": "missing_confirmation_token",
            "confirmation_required": False,
            "result": None,
            "error": "confirmation_token is required",
        }
    session_id = arguments.get("session_id", DEFAULT_MCP_SESSION_ID)
    request = app_module.ToolConfirmRequest(
        confirmation_token=token,
        session_id=str(session_id or DEFAULT_MCP_SESSION_ID),
    )
    return app_module.confirm_tool(request)


def _copy_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        return {"_invalid_arguments": arguments}
    return dict(arguments)


def _extract_session_id(arguments: dict[str, Any]) -> tuple[dict[str, Any], str]:
    tool_args = dict(arguments)
    session_id = tool_args.pop("session_id", DEFAULT_MCP_SESSION_ID)
    return tool_args, str(session_id or DEFAULT_MCP_SESSION_ID)


def _confirm_tool_schema() -> dict[str, Any]:
    return {
        "name": CONFIRM_TOOL_NAME,
        "description": "Confirm and execute a pending SafeOpsAgent dry-run tool call.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "confirmation_token": {
                    "type": "string",
                    "description": "One-time token returned by a confirm dry-run response.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional audit session id for this MCP confirmation.",
                },
            },
            "required": ["confirmation_token"],
        },
    }
