"""Controlled reversible-cleanup tools."""
from __future__ import annotations

from backend import config
from backend.cleanup import CleanupError, get_cleanup_service

from .registry import ToolResult, ToolSchema, get_registry


def _result(tool: str, action, *args) -> ToolResult:
    service = get_cleanup_service()
    try:
        data = action(*args)
    except (CleanupError, OSError) as exc:
        return ToolResult(
            tool=tool,
            status="command_failed",
            error=str(exc),
            audit={
                "actual_command": ["controlled_file_operation", tool],
                "executor_user": service.executor_user,
                "execution_success": False,
                "stderr_summary": str(exc)[:500],
            },
        )
    return ToolResult(
        tool=tool,
        status="success",
        data=data,
        audit={
            "actual_command": ["controlled_file_operation", tool],
            "executor_user": service.executor_user,
            "execution_success": True,
            "stdout_summary": _summary(tool, data),
        },
    )


def _scan(path: str = "/tmp", min_age_hours: int = 24, max_files: int = 50) -> ToolResult:
    service = get_cleanup_service()
    return _result("safe_cleanup_scan", service.scan, path, min_age_hours, max_files)


def _plan(path: str = "/tmp", min_age_hours: int = 24, max_files: int = 50) -> ToolResult:
    service = get_cleanup_service()
    return _result("safe_cleanup_plan", service.create_plan, path, min_age_hours, max_files)


def _quarantine(plan_id: str, plan_hash: str) -> ToolResult:
    service = get_cleanup_service()
    return _result("safe_cleanup_quarantine", service.quarantine, plan_id, plan_hash)


def _restore(quarantine_id: str, manifest_hash: str) -> ToolResult:
    service = get_cleanup_service()
    return _result("safe_cleanup_restore", service.restore, quarantine_id, manifest_hash)


def _summary(tool: str, data: dict) -> str:
    count = (
        data.get("candidate_count")
        or data.get("moved_count")
        or data.get("restored_count")
        or 0
    )
    return f"tool={tool}, files={count}, permanent_delete=false"


COMMON_PROPERTIES = {
    "path": {
        "type": "string",
        "description": "Directory under a configured temporary cleanup root",
        "minLength": 1,
        "maxLength": 500,
    },
    "min_age_hours": {
        "type": "integer",
        "description": "Only consider files older than this many hours",
        "minimum": 1,
        "maximum": 24 * 365,
        "default": config.SAFE_CLEANUP_MIN_AGE_HOURS,
    },
    "max_files": {
        "type": "integer",
        "description": "Maximum candidate files",
        "minimum": 1,
        "maximum": config.SAFE_CLEANUP_MAX_FILES,
        "default": config.SAFE_CLEANUP_MAX_FILES,
    },
}

SCAN_SCHEMA = ToolSchema(
    name="safe_cleanup_scan",
    description="Safely scan old temporary-file candidates without changing files",
    input_schema={"type": "object", "properties": COMMON_PROPERTIES, "required": []},
)
PLAN_SCHEMA = ToolSchema(
    name="safe_cleanup_plan",
    description="Create a hash-bound dry-run cleanup plan without changing files",
    input_schema={"type": "object", "properties": COMMON_PROPERTIES, "required": []},
)
QUARANTINE_SCHEMA = ToolSchema(
    name="safe_cleanup_quarantine",
    description="Move an unchanged cleanup plan into reversible same-filesystem quarantine",
    input_schema={
        "type": "object",
        "properties": {
            "plan_id": {
                "type": "string",
                "pattern": r"[a-f0-9]{32}",
                "minLength": 32,
                "maxLength": 32,
            },
            "plan_hash": {
                "type": "string",
                "pattern": r"[a-f0-9]{64}",
                "minLength": 64,
                "maxLength": 64,
            },
        },
        "required": ["plan_id", "plan_hash"],
    },
)
RESTORE_SCHEMA = ToolSchema(
    name="safe_cleanup_restore",
    description="Restore files from a verified SafeOpsAgent quarantine manifest",
    input_schema={
        "type": "object",
        "properties": {
            "quarantine_id": {
                "type": "string",
                "pattern": r"[a-f0-9]{32}",
                "minLength": 32,
                "maxLength": 32,
            },
            "manifest_hash": {
                "type": "string",
                "pattern": r"[a-f0-9]{64}",
                "minLength": 64,
                "maxLength": 64,
            },
        },
        "required": ["quarantine_id", "manifest_hash"],
    },
)


def register() -> None:
    registry = get_registry()
    registry.register(
        SCAN_SCHEMA,
        lambda path="/tmp", min_age_hours=24, max_files=50: _scan(
            path, min_age_hours, max_files
        ),
    )
    registry.register(
        PLAN_SCHEMA,
        lambda path="/tmp", min_age_hours=24, max_files=50: _plan(
            path, min_age_hours, max_files
        ),
    )
    registry.register(
        QUARANTINE_SCHEMA,
        lambda plan_id, plan_hash: _quarantine(plan_id, plan_hash),
    )
    registry.register(
        RESTORE_SCHEMA,
        lambda quarantine_id, manifest_hash: _restore(quarantine_id, manifest_hash),
    )
