"""Tool: get_port_usage - query which process listens on a port."""
import re

from backend.executor import SafeExecutor

from .registry import ToolResult, ToolSchema, command_audit, get_registry

_executor = SafeExecutor()


def _get_port_usage(port: int) -> ToolResult:
    if isinstance(port, bool) or not isinstance(port, int):
        return ToolResult(tool="get_port_usage", status="command_failed", error="port must be an integer")
    if port < 1 or port > 65535:
        return ToolResult(tool="get_port_usage", status="command_failed", error="port must be between 1 and 65535")

    attempts = [
        ("ss", ["ss", "-lntp"]),
        ("lsof", ["lsof", "-nP", "-i", f":{port}", "-sTCP:LISTEN"]),
        ("netstat", ["netstat", "-tulpn"]),
    ]
    errors = []
    for source, command in attempts:
        result = _executor.run(command)
        if not result.success:
            errors.append(f"{source}: {result.error or result.stderr}")
            continue

        listeners = _parse_port_output(source, result.stdout, port)
        return ToolResult(
            tool="get_port_usage",
            status="success",
            data={"port": port, "listeners": listeners},
            raw_output=result.stdout,
            audit=command_audit(result),
        )

    if errors and all("not found" in err.lower() for err in errors):
        status = "capability_missing"
    else:
        status = "command_failed"
    return ToolResult(
        tool="get_port_usage",
        status=status,
        data={"port": port, "listeners": []},
        error="; ".join(errors) or "No port query command available",
        audit=command_audit(result) if "result" in locals() else {},
    )


def _parse_port_output(source: str, output: str, port: int) -> list[dict]:
    if source == "ss":
        return _parse_ss(output, port)
    if source == "lsof":
        return _parse_lsof(output, port)
    if source == "netstat":
        return _parse_netstat(output, port)
    return []


def _parse_ss(output: str, port: int) -> list[dict]:
    listeners = []
    port_pattern = re.compile(rf"(^|[\[\]:.]){port}$")
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[3] if len(parts) >= 4 else ""
        process_info = " ".join(parts[5:]) if len(parts) > 5 else ""
        if not port_pattern.search(local_address):
            continue
        listeners.append({
            "protocol": parts[0],
            "local_address": local_address,
            "pid": _extract_pid(process_info),
            "process": _extract_process(process_info),
        })
    return listeners


def _parse_lsof(output: str, port: int) -> list[dict]:
    listeners = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 8:
            continue
        name = " ".join(parts[8:])
        if f":{port}" not in name:
            continue
        listeners.append({
            "protocol": parts[7] if len(parts) > 7 else "",
            "local_address": name,
            "pid": parts[1],
            "process": parts[0],
        })
    return listeners


def _parse_netstat(output: str, port: int) -> list[dict]:
    listeners = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4 or not parts[0].lower().startswith(("tcp", "udp")):
            continue
        local_address = parts[3]
        if not local_address.endswith(f":{port}"):
            continue
        pid_program = parts[-1] if len(parts) >= 7 else ""
        pid = ""
        process = ""
        if "/" in pid_program:
            pid, process = pid_program.split("/", 1)
        listeners.append({
            "protocol": parts[0],
            "local_address": local_address,
            "pid": pid,
            "process": process,
        })
    return listeners


def _extract_pid(process_info: str) -> str:
    match = re.search(r"pid=(\d+)", process_info)
    return match.group(1) if match else ""


def _extract_process(process_info: str) -> str:
    match = re.search(r'users:\(\("([^"]+)"', process_info)
    return match.group(1) if match else ""


SCHEMA = ToolSchema(
    name="get_port_usage",
    description="Query which process is listening on a TCP port",
    input_schema={
        "type": "object",
        "properties": {
            "port": {
                "type": "integer",
                "description": "TCP port number, 1-65535",
                "minimum": 1,
                "maximum": 65535,
            },
        },
        "required": ["port"],
    },
)


def register():
    get_registry().register(SCHEMA, lambda port: _get_port_usage(port))
