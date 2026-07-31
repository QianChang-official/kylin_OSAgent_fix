"""Tool: disk_usage - query disk space usage."""
from backend.executor import SafeExecutor

from .registry import ToolResult, ToolSchema, command_audit, get_registry

_executor = SafeExecutor()


def _disk_usage() -> ToolResult:
    result = _executor.run(["df", "-h"])
    if not result.success:
        status = "capability_missing" if "not found" in result.error.lower() else "command_failed"
        return ToolResult(
            tool="disk_usage",
            status=status,
            raw_output=result.stderr,
            error=result.error,
            audit=command_audit(result),
        )

    lines = result.stdout.strip().split("\n")
    if not lines:
        return ToolResult(tool="disk_usage", status="no_output", audit=command_audit(result))

    data = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6:
            try:
                usage_value = float(parts[4].rstrip("%"))
            except ValueError:
                usage_value = None
            data.append({
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
                "use_percent": parts[4],
                "mounted_on": parts[5],
                "usage_percent": usage_value,
                "status": (
                    "critical" if usage_value is not None and usage_value >= 95
                    else "warning" if usage_value is not None and usage_value >= 85
                    else "notice" if usage_value is not None and usage_value >= 75
                    else "normal"
                ),
            })
    return ToolResult(tool="disk_usage", status="success", data=data, raw_output=result.stdout, audit=command_audit(result))


SCHEMA = ToolSchema(
    name="disk_usage",
    description="Query disk space usage for all mounted filesystems",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def register():
    get_registry().register(SCHEMA, lambda: _disk_usage())
