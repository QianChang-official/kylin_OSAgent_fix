"""Tool: get_service_status - query systemd service status."""
import re

from backend.executor import SafeExecutor

from .registry import ToolResult, ToolSchema, command_audit, get_registry

_executor = SafeExecutor()
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")


def _get_service_status(service_name: str) -> ToolResult:
    valid, error = _validate_service_name(service_name)
    if not valid:
        return ToolResult(tool="get_service_status", status="command_failed", error=error)

    active_result = _executor.run(["systemctl", "is-active", service_name])
    enabled_result = _executor.run(["systemctl", "is-enabled", service_name])
    status_result = _executor.run(["systemctl", "status", service_name, "--no-pager"])

    if any(
        "command not found" in err.lower()
        for err in [active_result.error, enabled_result.error, status_result.error]
    ):
        return ToolResult(
            tool="get_service_status",
            status="capability_missing",
            data=_service_data(
                service_name,
                "",
                "",
                "",
                active_result,
                enabled_result,
                status_result,
            ),
            error="systemctl not available",
            audit=command_audit(status_result),
        )

    active_state = (active_result.stdout or active_result.stderr or "").strip().splitlines()
    active_state_text = active_state[0] if active_state else "unknown"
    enabled_state = (enabled_result.stdout or enabled_result.stderr or "").strip().splitlines()
    enabled_state_text = enabled_state[0] if enabled_state else "unknown"
    summary = _status_summary(status_result.stdout or status_result.stderr)
    status = "success" if active_result.success or status_result.stdout else "command_failed"
    data = _service_data(
        service_name,
        active_state_text,
        enabled_state_text,
        summary,
        active_result,
        enabled_result,
        status_result,
    )
    return ToolResult(
        tool="get_service_status",
        status=status,
        data=data,
        raw_output=status_result.stdout or status_result.stderr,
        error="" if status == "success" else (active_result.error or status_result.error),
        audit=command_audit(status_result),
    )


def _validate_service_name(service_name: str) -> tuple[bool, str]:
    if not isinstance(service_name, str):
        return False, "service_name must be a string"
    if not SERVICE_NAME_RE.fullmatch(service_name):
        return False, "service_name contains invalid characters or length"
    return True, ""


def _status_summary(output: str) -> str:
    if not output:
        return ""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return "\n".join(lines[:8])


def _service_data(
    service_name: str,
    active_state: str,
    enabled_state: str,
    summary: str,
    active_result,
    enabled_result,
    status_result,
) -> dict:
    return {
        "service_name": service_name,
        "active_state": active_state,
        "enabled_state": enabled_state,
        "status_summary": summary,
        "raw_output": status_result.stdout or status_result.stderr,
        "error": active_result.error or status_result.error or enabled_result.error,
    }


SCHEMA = ToolSchema(
    name="get_service_status",
    description="Query systemd service active state and status summary",
    input_schema={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "systemd service name, e.g. nginx or sshd.service",
                "pattern": r"[A-Za-z0-9_.@-]{1,64}",
                "minLength": 1,
                "maxLength": 64,
            },
        },
        "required": ["service_name"],
    },
)


def register():
    get_registry().register(SCHEMA, lambda service_name: _get_service_status(service_name))
