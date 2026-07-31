"""Tool: process_list - query running processes."""
from backend.executor import SafeExecutor

from .registry import ToolResult, ToolSchema, command_audit, get_registry

_executor = SafeExecutor()


def _process_list() -> ToolResult:
    cmds = [
        ["ps", "-eo", "pid,user,comm,%cpu,%mem,args", "--sort=-%cpu"],
        ["ps", "aux", "--sort=-%cpu"],
    ]
    last_error = ""
    for cmd in cmds:
        result = _executor.run(cmd)
        if not result.success:
            last_error = result.error or result.stderr
            continue
        lines = result.stdout.strip().split("\n")
        if not lines:
            return ToolResult(tool="process_list", status="no_output", audit=command_audit(result))
        data = []
        for line in lines[1:]:
            parts = line.split() if cmd[1] == "aux" else line.split(None, 5)
            if len(parts) >= 5:
                if cmd[1] == "aux":
                    data.append({
                        "user": parts[0],
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": parts[10] if len(parts) > 10 else parts[-1],
                    })
                else:
                    data.append({
                        "pid": parts[0],
                        "user": parts[1],
                        "name": parts[2],
                        "cpu": parts[3],
                        "mem": parts[4],
                        "command": parts[5] if len(parts) > 5 else parts[2],
                    })
        return ToolResult(
            tool="process_list",
            status="success",
            data=data[:20],
            raw_output=result.stdout,
            audit=command_audit(result),
        )
    status = "capability_missing" if "not found" in last_error.lower() else "command_failed"
    return ToolResult(
        tool="process_list",
        status=status,
        error=last_error or "ps not available",
        audit=command_audit(result) if "result" in locals() else {},
    )


SCHEMA = ToolSchema(
    name="process_list",
    description="Query running processes sorted by CPU usage",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def register():
    get_registry().register(SCHEMA, lambda: _process_list())
