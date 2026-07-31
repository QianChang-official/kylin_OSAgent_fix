"""Tool: get_cpu_status - read CPU and load metrics on Linux/Kylin."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from backend import config
from backend.executor import SafeExecutor

from .registry import ToolResult, ToolSchema, command_audit, get_registry

_executor = SafeExecutor()
PROC_STAT = Path("/proc/stat")
PROC_LOADAVG = Path("/proc/loadavg")
PROC_CPUINFO = Path("/proc/cpuinfo")


def _get_cpu_status() -> ToolResult:
    sample_interval = min(1.0, max(0.01, float(config.CPU_SAMPLE_INTERVAL_SECONDS)))
    if not (PROC_STAT.is_file() and PROC_LOADAVG.is_file() and PROC_CPUINFO.is_file()):
        return ToolResult(
            tool="get_cpu_status",
            status="capability_missing",
            data={
                "usage_percent": None,
                "usage_sample_kind": "instantaneous",
                "sample_interval_seconds": sample_interval,
                "logical_cores": None,
                "physical_cores": None,
                "load_1m": None,
                "load_5m": None,
                "load_15m": None,
                "load_per_core": None,
                "top_processes": [],
                "status": "environment_limited",
            },
            error="Linux /proc CPU metrics are not available",
        )

    try:
        first = _read_cpu_times(PROC_STAT.read_text(encoding="utf-8", errors="replace"))
        time.sleep(sample_interval)
        second = _read_cpu_times(PROC_STAT.read_text(encoding="utf-8", errors="replace"))
        usage = _usage_percent(first, second)
        load_1m, load_5m, load_15m = _parse_loadavg(
            PROC_LOADAVG.read_text(encoding="utf-8", errors="replace")
        )
        cpuinfo = PROC_CPUINFO.read_text(encoding="utf-8", errors="replace")
        logical_cores, physical_cores = _parse_cpuinfo(cpuinfo)
    except (OSError, ValueError) as exc:
        return ToolResult(
            tool="get_cpu_status",
            status="parse_warning",
            data={
                "usage_percent": None,
                "usage_sample_kind": "instantaneous",
                "sample_interval_seconds": sample_interval,
                "logical_cores": None,
                "physical_cores": None,
                "load_1m": None,
                "load_5m": None,
                "load_15m": None,
                "load_per_core": None,
                "top_processes": [],
                "status": "unavailable",
            },
            error=f"Unable to read CPU metrics: {exc}",
        )

    process_result = _executor.run(
        ["ps", "-eo", "pid,user,comm,%cpu,%mem", "--sort=-%cpu"]
    )
    top_processes = _parse_processes(process_result.stdout) if process_result.success else []
    load_per_core = round(load_1m / logical_cores, 3) if logical_cores else None
    data = {
        "usage_percent": usage,
        "usage_sample_kind": "instantaneous",
        "sample_interval_seconds": sample_interval,
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
        "load_1m": load_1m,
        "load_5m": load_5m,
        "load_15m": load_15m,
        "load_per_core": load_per_core,
        "top_processes": top_processes,
        "status": "available",
    }
    audit = command_audit(process_result)
    audit["metric_sources"] = ["/proc/stat", "/proc/loadavg", "/proc/cpuinfo"]
    audit["sample_interval_seconds"] = sample_interval
    status = "success" if process_result.success else "parse_warning"
    return ToolResult(
        tool="get_cpu_status",
        status=status,
        data=data,
        raw_output=process_result.stdout,
        error="" if process_result.success else (process_result.error or "ps unavailable"),
        audit=audit,
    )


def _read_cpu_times(text: str) -> tuple[int, int]:
    first_line = next((line for line in text.splitlines() if line.startswith("cpu ")), "")
    parts = first_line.split()
    if len(parts) < 5:
        raise ValueError("aggregate cpu line not found")
    values = [int(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    # guest and guest_nice are already included in user and nice on Linux.
    # Excluding them avoids double-counting virtual CPU time.
    return sum(values[:8]), idle


def _usage_percent(first: tuple[int, int], second: tuple[int, int]) -> float:
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        raise ValueError("CPU sample interval produced no measurable delta")
    return round(max(0.0, min(100.0, (total_delta - idle_delta) / total_delta * 100)), 1)


def _parse_loadavg(text: str) -> tuple[float, float, float]:
    parts = text.split()
    if len(parts) < 3:
        raise ValueError("loadavg format is incomplete")
    return float(parts[0]), float(parts[1]), float(parts[2])


def _parse_cpuinfo(text: str) -> tuple[int, int | None]:
    blocks = [block for block in text.split("\n\n") if block.strip()]
    logical = len(blocks) or (os.cpu_count() or 0)
    physical_pairs: set[tuple[str, str]] = set()
    for block in blocks:
        values: dict[str, str] = {}
        for line in block.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip().lower()] = value.strip()
        physical_id = values.get("physical id")
        core_id = values.get("core id")
        if physical_id is not None and core_id is not None:
            physical_pairs.add((physical_id, core_id))
    return logical, len(physical_pairs) if physical_pairs else None


def _parse_processes(output: str) -> list[dict[str, Any]]:
    processes = []
    for line in output.splitlines()[1:]:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        processes.append({
            "pid": parts[0],
            "user": parts[1],
            "name": parts[2],
            "cpu": _safe_float(parts[3]),
            "mem": _safe_float(parts[4]),
        })
        if len(processes) >= 10:
            break
    return processes


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


SCHEMA = ToolSchema(
    name="get_cpu_status",
    description="Query CPU usage, load average, core count, and top CPU processes",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def register() -> None:
    get_registry().register(SCHEMA, lambda: _get_cpu_status())
