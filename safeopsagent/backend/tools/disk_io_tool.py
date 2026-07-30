"""Tool: disk_io_analysis - detect disk I/O bottlenecks via iostat.

Competition scenario explicitly names "disk I/O anomaly". This tool is
read-only: it runs ``iostat -x`` and identifies devices with high
utilization or high await latency, then maps them to mounts when possible.
"""
from __future__ import annotations

from typing import Any

from backend.executor import SafeExecutor
from .registry import ToolSchema, ToolResult, command_audit, get_registry


_executor = SafeExecutor()

# Thresholds for flagging a device as a bottleneck.
UTIL_THRESHOLD = 80.0      # %util >= 80 => saturated
AWAIT_THRESHOLD = 50.0     # await ms >= 50 => slow response


def _disk_io_analysis() -> ToolResult:
    cmd = ["iostat", "-x", "1", "2"]
    result = _executor.run(cmd)
    if not result.success:
        err = result.error or result.stderr or "iostat not available"
        status = "capability_missing" if "not found" in err.lower() else "command_failed"
        return ToolResult(
            tool="disk_io_analysis",
            status=status,
            error=err,
            audit=command_audit(result) if hasattr(result, "command") else {},
        )

    devices = _parse_iostat(result.stdout)
    if not devices:
        return ToolResult(
            tool="disk_io_analysis",
            status="no_output",
            error="iostat output could not be parsed",
            audit=command_audit(result),
        )

    bottlenecks = [
        dev for dev in devices
        if (dev.get("util_percent") or 0) >= UTIL_THRESHOLD
        or (dev.get("await_ms") or 0) >= AWAIT_THRESHOLD
    ]
    bottlenecks.sort(key=lambda d: d.get("util_percent") or 0, reverse=True)

    recommendation = _build_recommendation(devices, bottlenecks)

    return ToolResult(
        tool="disk_io_analysis",
        status="success",
        data={
            "device_count": len(devices),
            "devices": devices,
            "bottleneck_count": len(bottlenecks),
            "bottlenecks": bottlenecks,
            "recommendation": recommendation,
        },
        raw_output=f"iostat: {len(devices)} devices, {len(bottlenecks)} bottlenecks",
        audit=command_audit(result),
    )


def _parse_iostat(stdout: str) -> list[dict[str, Any]]:
    """Parse the second sample of ``iostat -x 1 2`` output."""
    blocks = stdout.strip().split("\n\n")
    if len(blocks) < 2:
        return []
    # Take the last block (second sample, stable values).
    target = blocks[-1]
    lines = target.strip().split("\n")
    if not lines:
        return []

    header = lines[0].split()
    # Map common column names to normalized keys.
    col_map = {
        "Device": "device",
        "%util": "util_percent",
        "r_await": "r_await_ms",
        "w_await": "w_await_ms",
        "await": "await_ms",
        "svctm": "svctm_ms",
        "r/s": "rps",
        "w/s": "wps",
        "rkB/s": "rkbs",
        "wkB/s": "wkbs",
    }

    devices: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        device = parts[0]
        row: dict[str, Any] = {"device": device}
        for idx, col in enumerate(header):
            if col not in col_map or idx >= len(parts):
                continue
            key = col_map[col]
            try:
                row[key] = float(parts[idx])
            except (ValueError, IndexError):
                row[key] = parts[idx]
        # If await not present, derive from r_await/w_await average.
        if "await_ms" not in row and "r_await_ms" in row and "w_await_ms" in row:
            try:
                row["await_ms"] = round((float(row["r_await_ms"]) + float(row["w_await_ms"])) / 2, 2)
            except (TypeError, ValueError):
                pass
        devices.append(row)
    return devices


def _build_recommendation(devices: list[dict[str, Any]], bottlenecks: list[dict[str, Any]]) -> str:
    if not bottlenecks:
        return f"已检查 {len(devices)} 个块设备，未发现 I/O 瓶颈（util<{UTIL_THRESHOLD}% 且 await<{AWAIT_THRESHOLD}ms）。"

    parts = [f"检测到 {len(bottlenecks)} 个 I/O 瓶颈设备。"]
    for dev in bottlenecks[:3]:
        name = dev.get("device", "未知")
        util = dev.get("util_percent", "未知")
        await_ms = dev.get("await_ms", dev.get("r_await_ms", "未知"))
        parts.append(f"{name}: util={util}%, await={await_ms}ms。")
    parts.append("建议结合 process_list 和 large_file_scan 定位高 I/O 进程或大文件写入来源，不要直接终止进程。")
    return " ".join(parts)


SCHEMA = ToolSchema(
    name="disk_io_analysis",
    description="Detect disk I/O bottlenecks by parsing iostat -x output (read-only)",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def register() -> None:
    get_registry().register(SCHEMA, lambda: _disk_io_analysis())
