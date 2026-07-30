"""Tool: impact_analysis - predict the blast radius of touching a file.

Classifying a file as "safe to clean" answers whether it *may* be
removed. It does not answer what happens if you do. This tool closes that
gap: before any cleanup decision, it enumerates which processes hold the
file open, which services own those processes, and which listening ports
those services serve.

The most valuable output is the handle-leak warning. Deleting a log file
that a running process still holds open does not release the disk space —
the inode survives until the process closes or restarts the descriptor.
Operators hit this constantly: `rm` the big log, watch df report no change,
then escalate. Predicting it beforehand turns a failed cleanup into a
correct one (truncate or logrotate instead of rm).

Read-only: lsof and ps only. This tool never modifies anything.
"""
from __future__ import annotations

import os
from typing import Any

from backend.executor import SafeExecutor
from .registry import ToolSchema, ToolResult, command_audit, get_registry


_executor = SafeExecutor()

MAX_HOLDERS = 20

# File categories whose removal has consequences beyond disk space.
APPEND_ONLY_HINTS = (".log", ".out", ".err", ".nohup")


def _impact_analysis(path: str) -> ToolResult:
    if not path or not isinstance(path, str):
        return ToolResult(
            tool="impact_analysis",
            status="command_failed",
            error="path is required",
        )

    exists = os.path.exists(path)
    size_bytes = None
    if exists:
        try:
            size_bytes = os.path.getsize(path)
        except OSError:
            size_bytes = None

    holders, holder_status, audit = _find_holders(path)
    services = _resolve_services(holders)
    ports = _resolve_ports(holders)
    assessment = _assess(path, exists, size_bytes, holders, services, ports)

    return ToolResult(
        tool="impact_analysis",
        status=holder_status,
        data={
            "path": path,
            "exists": exists,
            "size_bytes": size_bytes,
            "size_human": _human_size(size_bytes),
            "holder_count": len(holders),
            "holders": holders,
            "affected_services": services,
            "affected_ports": ports,
            "blast_radius": assessment["blast_radius"],
            "handle_leak_risk": assessment["handle_leak_risk"],
            "safe_action": assessment["safe_action"],
            "severity": assessment["severity"],
            "warnings": assessment["warnings"],
            "recommendation": assessment["recommendation"],
        },
        raw_output=f"impact_analysis {path}: {len(holders)} holders, {len(services)} services",
        audit=audit,
    )


def _find_holders(path: str) -> tuple[list[dict[str, Any]], str, dict]:
    """Processes currently holding the path open, via lsof."""
    result = _executor.run(["lsof", "--", path])
    audit = command_audit(result) if hasattr(result, "command") else {}

    if not result.success:
        error = (result.error or result.stderr or "").lower()
        # lsof exits non-zero when nothing holds the file — that is a valid
        # answer (no holders), not a failure.
        if "not found" in error or "no such file" in error and "lsof" in error:
            return [], "capability_missing", audit
        if not result.stdout.strip():
            return [], "success", audit

    holders: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines()[1:]:
        parts = line.split(None, 8)
        if len(parts) < 4:
            continue
        holders.append({
            "command": parts[0],
            "pid": parts[1],
            "user": parts[2],
            "fd": parts[3],
            "type": parts[4] if len(parts) > 4 else "",
        })
        if len(holders) >= MAX_HOLDERS:
            break
    return holders, "success", audit


def _resolve_services(holders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map holding processes to their owning systemd units."""
    services: dict[str, dict[str, Any]] = {}
    for holder in holders:
        pid = holder.get("pid", "")
        if not pid:
            continue
        unit = _systemd_unit_for(pid)
        name = unit or holder.get("command", "unknown")
        entry = services.setdefault(name, {
            "name": name,
            "systemd_unit": unit,
            "pids": [],
            "managed_by_systemd": bool(unit),
        })
        entry["pids"].append(pid)
    return sorted(services.values(), key=lambda item: item["name"])


def _systemd_unit_for(pid: str) -> str:
    """Read the cgroup entry to find the owning systemd unit (read-only)."""
    try:
        content = open(f"/proc/{pid}/cgroup", encoding="utf-8").read()
    except OSError:
        return ""
    for line in content.splitlines():
        if ".service" not in line:
            continue
        for segment in line.replace("\\x2d", "-").split("/"):
            if segment.endswith(".service"):
                return segment
    return ""


def _resolve_ports(holders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Listening ports served by the holding processes."""
    pids = {holder.get("pid") for holder in holders if holder.get("pid")}
    if not pids:
        return []

    result = _executor.run(["ss", "-lntup"])
    if not result.success:
        return []

    ports: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line in result.stdout.splitlines()[1:]:
        if "pid=" not in line:
            continue
        matched_pid = next((pid for pid in pids if f"pid={pid}," in line or f"pid={pid})" in line), None)
        if not matched_pid:
            continue
        parts = line.split()
        local = next((item for item in parts if ":" in item and not item.startswith("users:")), "")
        port = local.rsplit(":", 1)[-1] if local else ""
        key = (matched_pid, port)
        if not port or key in seen:
            continue
        seen.add(key)
        ports.append({"pid": matched_pid, "port": port, "local_address": local})
    return ports


def _assess(path: str, exists: bool, size_bytes: int | None,
            holders: list[dict[str, Any]], services: list[dict[str, Any]],
            ports: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    lowered = path.lower()
    looks_append_only = any(lowered.endswith(suffix) for suffix in APPEND_ONLY_HINTS)

    if not exists:
        return {
            "blast_radius": "none",
            "handle_leak_risk": False,
            "safe_action": "no_action",
            "severity": "info",
            "warnings": ["路径不存在，无需处置"],
            "recommendation": f"{path} 不存在，无影响面。",
        }

    handle_leak_risk = bool(holders)
    if handle_leak_risk:
        warnings.append(
            f"该文件正被 {len(holders)} 个进程持有句柄，直接 rm 删除后 inode 不会释放，"
            f"磁盘空间不会立即回收（典型的“删了但 df 没变”陷阱）"
        )
    if services:
        managed = [item["name"] for item in services if item["managed_by_systemd"]]
        if managed:
            warnings.append(f"影响 systemd 托管服务：{'、'.join(managed)}")
    if ports:
        port_list = "、".join(sorted({item["port"] for item in ports}))
        warnings.append(f"相关进程正在监听端口 {port_list}，处置不当可能中断对外服务")

    if not holders:
        blast_radius = "isolated"
        severity = "info"
        safe_action = "safe_to_remove"
        recommendation = (
            f"{path}（{_human_size(size_bytes)}）当前没有进程持有句柄，"
            f"可纳入 safe_cleanup_plan 走 dry-run + 人工确认的可恢复隔离流程。"
        )
    elif looks_append_only:
        blast_radius = "service_local"
        severity = "warning"
        safe_action = "truncate_or_logrotate"
        recommendation = (
            f"{path}（{_human_size(size_bytes)}）正被 "
            f"{'、'.join(item['command'] for item in holders[:3])} 持有。"
            f"这是追加写日志，**不要直接 rm**：应使用 truncate（`: > 文件`）或配置 logrotate 的 "
            f"copytruncate，让进程继续写入同一 inode，空间才会真正释放。"
        )
    else:
        blast_radius = "service_impacting"
        severity = "critical"
        safe_action = "manual_review"
        recommendation = (
            f"{path}（{_human_size(size_bytes)}）正被运行中的进程持有，且不是可安全截断的日志文件。"
            f"删除可能导致服务异常，建议先停止或重启相关服务，再由管理员人工评估。"
        )

    if len(services) > 1:
        blast_radius = "multi_service"
        severity = "critical"

    return {
        "blast_radius": blast_radius,
        "handle_leak_risk": handle_leak_risk,
        "safe_action": safe_action,
        "severity": severity,
        "warnings": warnings,
        "recommendation": recommendation,
    }


def _human_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "未知"
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{value:.1f}TB"


SCHEMA = ToolSchema(
    name="impact_analysis",
    description=(
        "Predict the blast radius of removing a file: holding processes, "
        "affected services and ports, and handle-leak risk (read-only)"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path of the file to analyse",
                "maxLength": 4096,
            },
        },
        "required": ["path"],
    },
)


def register() -> None:
    get_registry().register(SCHEMA, lambda path: _impact_analysis(path))
