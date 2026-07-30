"""Tool: network_status - query listening ports and connections."""
import re
import shutil

from backend.executor import SafeExecutor
from .registry import ToolSchema, ToolResult, command_audit, get_registry


_executor = SafeExecutor()


def _network_status() -> ToolResult:
    cmds = []
    if shutil.which("ss"):
        cmds.append(["ss", "-tulnp"])
    if shutil.which("netstat"):
        cmds.append(["netstat", "-tulpn"])
    if not cmds:
        return ToolResult(
            tool="network_status",
            status="capability_missing",
            error="Neither ss nor netstat available",
        )

    last_error = ""
    for cmd in cmds:
        result = _executor.run(cmd)
        if not result.success:
            last_error = result.error or result.stderr
            continue
        lines = result.stdout.strip().split("\n")
        if not lines:
            return ToolResult(tool="network_status", status="no_output", audit=command_audit(result))
        data = []
        is_ss = cmd[0] == "ss"
        for line in lines[1:]:
            parts = line.split()
            if is_ss and len(parts) >= 5:
                process_info = " ".join(parts[6:]) if len(parts) > 6 else ""
                data.append({
                    "protocol": parts[0],
                    "state": parts[1],
                    "recv_q": "",
                    "send_q": "",
                    "local": parts[4],
                    "peer": parts[5] if len(parts) > 5 else "",
                    "pid": _extract_pid(process_info),
                    "process": _extract_process(process_info),
                })
            elif not is_ss and len(parts) >= 4:
                pid, process = _netstat_process(parts[-1]) if len(parts) >= 7 else ("", "")
                data.append({
                    "protocol": parts[0],
                    "recv_q": parts[1],
                    "send_q": parts[2],
                    "local": parts[3],
                    "state": "LISTEN" if "LISTEN" in line else "",
                    "pid": pid,
                    "process": process,
                })
        return ToolResult(
            tool="network_status",
            status="success",
            data=data,
            raw_output=result.stdout,
            audit=command_audit(result),
        )
    return ToolResult(
        tool="network_status",
        status="command_failed",
        error=last_error or "All network commands failed",
        audit=command_audit(result) if "result" in locals() else {},
    )


SCHEMA = ToolSchema(
    name="network_status",
    description="Query listening TCP/UDP ports",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def _extract_pid(value: str) -> str:
    match = re.search(r"pid=(\d+)", value)
    return match.group(1) if match else ""


def _extract_process(value: str) -> str:
    match = re.search(r'users:\(\("([^"]+)"', value)
    return match.group(1) if match else ""


def _netstat_process(value: str) -> tuple[str, str]:
    if "/" not in value:
        return "", ""
    pid, process = value.split("/", 1)
    return pid, process


def register():
    get_registry().register(SCHEMA, lambda: _network_status())
