"""Tool: get_memory_status - query memory usage via free."""
from backend.executor import SafeExecutor
from .registry import ToolSchema, ToolResult, command_audit, get_registry


_executor = SafeExecutor()


def _get_memory_status() -> ToolResult:
    result = _executor.run(["free", "-m"])
    if not result.success:
        status = "capability_missing" if "not found" in result.error.lower() else "command_failed"
        return ToolResult(
            tool="get_memory_status",
            status=status,
            raw_output=result.stderr,
            error=result.error,
            audit=command_audit(result),
        )

    data, error = _parse_free_m(result.stdout)
    if error:
        return ToolResult(
            tool="get_memory_status",
            status="parse_warning",
            data=data,
            raw_output=result.stdout,
            error=error,
            audit=command_audit(result),
        )
    return ToolResult(
        tool="get_memory_status",
        status="success",
        data=data,
        raw_output=result.stdout,
        audit=command_audit(result),
    )


def _parse_free_m(output: str) -> tuple[dict, str]:
    data = {
        "total_mb": None,
        "used_mb": None,
        "free_mb": None,
        "available_mb": None,
        "swap_total_mb": None,
        "swap_used_mb": None,
        "usage_percent": None,
        "swap_usage_percent": None,
    }
    try:
        for line in output.splitlines():
            parts = line.split()
            if not parts:
                continue
            label = parts[0].rstrip(":").lower()
            if label == "mem":
                if len(parts) < 4:
                    return data, "Unexpected Mem line format"
                data["total_mb"] = int(parts[1])
                data["used_mb"] = int(parts[2])
                data["free_mb"] = int(parts[3])
                if len(parts) >= 7:
                    data["available_mb"] = int(parts[6])
            elif label == "swap":
                if len(parts) >= 3:
                    data["swap_total_mb"] = int(parts[1])
                    data["swap_used_mb"] = int(parts[2])
        if data["total_mb"] is None:
            return data, "Mem line not found"
        if data["total_mb"]:
            data["usage_percent"] = round(data["used_mb"] / data["total_mb"] * 100, 1)
        if data["swap_total_mb"]:
            data["swap_usage_percent"] = round(
                data["swap_used_mb"] / data["swap_total_mb"] * 100,
                1,
            )
        elif data["swap_total_mb"] == 0:
            data["swap_usage_percent"] = 0.0
    except ValueError as exc:
        return data, f"Failed to parse memory values: {exc}"
    return data, ""


SCHEMA = ToolSchema(
    name="get_memory_status",
    description="Query system memory status in MB",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def register():
    get_registry().register(SCHEMA, lambda: _get_memory_status())
