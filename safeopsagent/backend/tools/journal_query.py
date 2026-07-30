"""Tool: journal_query - query system logs via journalctl."""
import re
import shutil

from backend.executor import SafeExecutor
from .registry import ToolSchema, ToolResult, command_audit, get_registry


_executor = SafeExecutor()
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")
MIN_LINES = 1
MAX_LINES = 500


def _journal_query(lines: int = 50, service: str = "") -> ToolResult:
    valid, error = _validate_journal_args(lines, service)
    if not valid:
        return ToolResult(tool="journal_query", status="command_failed", error=error)

    if not shutil.which("journalctl"):
        return ToolResult(tool="journal_query", status="capability_missing", error="journalctl not available")

    cmd = ["journalctl", "-n", str(lines), "--no-pager"]
    if service:
        cmd.extend(["-u", service])

    result = _executor.run(cmd)
    if not result.success:
        return ToolResult(
            tool="journal_query",
            status="command_failed",
            raw_output=result.stderr,
            error=result.error,
            audit=command_audit(result),
        )

    output = result.stdout.strip()
    if not output:
        return ToolResult(tool="journal_query", status="no_output", audit=command_audit(result))
    log_lines = output.split("\n")
    data = [_parse_log_line(i + 1, line) for i, line in enumerate(log_lines)]
    return ToolResult(tool="journal_query", status="success", data=data, raw_output=output, audit=command_audit(result))


def _validate_journal_args(lines: int, service: str) -> tuple[bool, str]:
    if isinstance(lines, bool) or not isinstance(lines, int):
        return False, "lines must be an integer"
    if lines < MIN_LINES or lines > MAX_LINES:
        return False, f"lines must be between {MIN_LINES} and {MAX_LINES}"
    if service is None:
        service = ""
    if not isinstance(service, str):
        return False, "service must be a string"
    if service and not SERVICE_NAME_RE.fullmatch(service):
        return False, "service contains invalid characters or length"
    return True, ""


def _parse_log_line(line_number: int, line: str) -> dict:
    parts = line.split()
    timestamp = " ".join(parts[:3]) if len(parts) >= 3 else ""
    source = parts[4].rstrip(":") if len(parts) >= 5 else ""
    lowered = line.lower()
    level = (
        "critical" if any(token in lowered for token in ["critical", "emerg", "panic"])
        else "error" if any(token in lowered for token in ["error", "failed"])
        else "warning" if "warning" in lowered or "warn" in lowered
        else "info"
    )
    return {
        "line": line_number,
        "timestamp": timestamp,
        "level": level,
        "source": source,
        "content": line,
    }


SCHEMA = ToolSchema(
    name="journal_query",
    description="Query recent system logs via journalctl",
    input_schema={
        "type": "object",
        "properties": {
            "lines": {
                "type": "integer",
                "description": "Number of lines to retrieve",
                "minimum": MIN_LINES,
                "maximum": MAX_LINES,
            },
            "service": {
                "type": "string",
                "description": "Service unit name (optional)",
                "pattern": r"[A-Za-z0-9_.@-]{0,64}",
                "maxLength": 64,
            },
        },
        "required": [],
    },
)


def register():
    get_registry().register(SCHEMA, lambda lines=50, service="": _journal_query(lines, service))
