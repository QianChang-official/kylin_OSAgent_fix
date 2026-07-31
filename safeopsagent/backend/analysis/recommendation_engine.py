"""Build factual diagnoses from validated ToolResult payloads.

The model may improve wording elsewhere, but this module owns metrics,
severity, findings, and recommendations returned by the public API.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .root_cause_engine import build_root_cause_chains

SEVERITY_ORDER = {
    "unknown": 0,
    "normal": 1,
    "notice": 2,
    "warning": 3,
    "critical": 4,
}

THRESHOLDS = {
    "memory_usage": (70.0, 80.0, 90.0),
    "available_memory_ratio": (15.0, 10.0, 5.0),
    "swap_usage": (20.0, 50.0, 80.0),
    "cpu_usage": (70.0, 85.0, 95.0),
    "load_per_core": (0.7, 1.0, 2.0),
    "disk_usage": (75.0, 85.0, 95.0),
    "process_cpu": (50.0, 75.0, 95.0),
}


@dataclass
class DiagnosisBuilder:
    severity: str = "unknown"
    findings: list[str] | None = None
    recommendations: list[str] | None = None
    next_actions: list[str] | None = None
    evidence: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        self.findings = []
        self.recommendations = []
        self.next_actions = []
        self.evidence = []

    def raise_severity(self, severity: str) -> None:
        if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(self.severity, 0):
            self.severity = severity

    def finding(self, text: str, severity: str = "normal") -> None:
        if text and text not in self.findings:
            self.findings.append(text)
        self.raise_severity(severity)

    def recommend(self, text: str) -> None:
        if text and text not in self.recommendations:
            self.recommendations.append(text)

    def next(self, text: str) -> None:
        if text and text not in self.next_actions:
            self.next_actions.append(text)

    def metric(
        self,
        metric: str,
        value: Any,
        unit: str,
        source_tool: str,
        *,
        context: str = "",
    ) -> None:
        if value is None:
            return
        item = {
            "metric": metric,
            "value": value,
            "unit": unit,
            "source_tool": source_tool,
        }
        if context:
            item["context"] = context
        self.evidence.append(item)


def build_diagnosis(
    tool_results: list[dict[str, Any]] | None,
    *,
    execution_status: str = "",
    security_decision: str = "",
    security_summary: str = "",
) -> dict[str, Any]:
    """Return a stable diagnosis object without inventing missing metrics."""
    builder = DiagnosisBuilder()
    handlers: dict[str, Callable[[DiagnosisBuilder, Any], None]] = {
        "get_memory_status": _memory,
        "get_cpu_status": _cpu,
        "disk_usage": _disk,
        "process_list": _processes,
        "network_status": _network,
        "get_port_usage": _port,
        "get_service_status": _service,
        "journal_query": _journal,
        "large_file_scan": _large_files,
        "safe_cleanup_scan": _cleanup_scan,
        "safe_cleanup_plan": _cleanup_plan,
        "safe_cleanup_quarantine": _cleanup_quarantine,
        "safe_cleanup_restore": _cleanup_restore,
        "config_drift_check": _config_drift,
        "zombie_process_check": _zombie_process,
        "disk_io_analysis": _disk_io,
        "impact_analysis": _impact,
    }

    usable_results = 0
    for result in tool_results or []:
        if not isinstance(result, dict):
            continue
        tool = str(result.get("tool", ""))
        status = str(result.get("status", ""))
        data = result.get("data")
        if status == "capability_missing":
            builder.finding(f"{tool or '系统检查'} 在当前环境中不可用。", "unknown")
            builder.next("请在银河麒麟、Linux 或 WSL 环境补充验证该项能力。")
            continue
        if status not in {"success", "parse_warning", "no_output"}:
            builder.finding(f"{tool or '系统检查'} 未获得有效结果。", "unknown")
            continue
        handler = handlers.get(tool)
        if handler is not None:
            handler(builder, data)
            usable_results += 1

    if security_decision in {"reject", "forbidden"}:
        summary = security_summary or "请求已被安全策略拒绝，未执行系统操作。"
        return {
            "summary": summary,
            "severity": "unknown",
            "findings": [summary],
            "recommendations": ["请改用明确的只读检查请求。"],
            "next_actions": ["查看 Audit Trace 了解命中规则和安全决策。"],
            "evidence": [],
            "root_cause_chains": [],
        }

    if usable_results == 0 or not builder.evidence:
        summary = _unknown_summary(execution_status, security_summary)
        return {
            "summary": summary,
            "severity": "unknown",
            "findings": builder.findings or [summary],
            "recommendations": builder.recommendations,
            "next_actions": builder.next_actions,
            "evidence": [],
            "root_cause_chains": [],
        }

    if builder.severity == "unknown":
        builder.severity = "normal"
    summary = _summary_from_findings(builder.findings, builder.severity)
    root_cause_chains = build_root_cause_chains(tool_results)
    return {
        "summary": summary,
        "severity": builder.severity,
        "findings": builder.findings,
        "recommendations": builder.recommendations,
        "next_actions": builder.next_actions,
        "evidence": builder.evidence,
        "root_cause_chains": root_cause_chains,
    }


def _memory(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    total = _number(data.get("total_mb"))
    used = _number(data.get("used_mb"))
    available = _number(data.get("available_mb"))
    free = _number(data.get("free_mb"))
    swap_total = _number(data.get("swap_total_mb"))
    swap_used = _number(data.get("swap_used_mb"))
    usage = _percent(used, total)
    available_ratio = _percent(available, total)
    swap_usage = _percent(swap_used, swap_total)

    for metric, value, unit in [
        ("memory_total", total, "MB"),
        ("memory_used", used, "MB"),
        ("memory_available", available, "MB"),
        ("memory_free", free, "MB"),
        ("memory_usage_percent", usage, "%"),
        ("swap_total", swap_total, "MB"),
        ("swap_used", swap_used, "MB"),
        ("swap_usage_percent", swap_usage, "%"),
    ]:
        builder.metric(metric, value, unit, "get_memory_status")

    if usage is None:
        return
    severity = _ascending_severity(usage, THRESHOLDS["memory_usage"])
    available_text = _format_mb(available)
    swap_text = _format_percent(swap_usage)
    builder.finding(
        f"当前内存使用率 {usage:.1f}%，可用内存 {available_text}，Swap 使用率 {swap_text}。",
        severity,
    )
    if available_ratio is not None and available_ratio <= THRESHOLDS["available_memory_ratio"][1]:
        builder.raise_severity("warning" if available_ratio > 5 else "critical")
        builder.recommend("可用内存偏低，建议结合高占用进程检查内存来源。")
        builder.next("查看高内存进程和近期服务变化。")
    elif severity in {"warning", "critical"}:
        builder.recommend("内存压力较高，建议检查高内存进程及 Swap 活动。")
        builder.next("调用 process_list 对比高占用进程。")
    else:
        builder.recommend("暂未发现明显内存压力，继续观察可用内存和 Swap 变化。")


def _cpu(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    usage = _number(data.get("usage_percent"))
    logical = _number(data.get("logical_cores"))
    physical = _number(data.get("physical_cores"))
    load_1m = _number(data.get("load_1m"))
    load_5m = _number(data.get("load_5m"))
    load_15m = _number(data.get("load_15m"))
    load_per_core = _number(data.get("load_per_core"))
    top_processes = [
        item for item in data.get("top_processes", [])
        if isinstance(item, dict)
    ]
    top_process = max(
        top_processes,
        key=lambda item: _number(item.get("cpu")) or 0.0,
        default=None,
    )
    top_process_cpu = _number(top_process.get("cpu")) if top_process else None
    top_process_name = str(
        (top_process or {}).get("name") or (top_process or {}).get("command") or ""
    )
    for metric, value, unit in [
        ("cpu_usage_percent", usage, "%"),
        ("cpu_logical_cores", logical, "cores"),
        ("cpu_physical_cores", physical, "cores"),
        ("load_1m", load_1m, ""),
        ("load_5m", load_5m, ""),
        ("load_15m", load_15m, ""),
        ("load_per_core", load_per_core, ""),
    ]:
        builder.metric(metric, value, unit, "get_cpu_status")
    builder.metric(
        "top_cpu_process_percent",
        top_process_cpu,
        "%",
        "get_cpu_status",
        context=top_process_name,
    )
    if usage is None:
        return
    usage_severity = _ascending_severity(usage, THRESHOLDS["cpu_usage"])
    load_severity = _ascending_severity(load_per_core, THRESHOLDS["load_per_core"])
    process_severity = _ascending_severity(top_process_cpu, THRESHOLDS["process_cpu"])
    corroborating_severity = _max_severity(load_severity, process_severity)
    if usage_severity in {"warning", "critical"} and corroborating_severity in {
        "unknown",
        "normal",
    }:
        severity = "notice"
    else:
        severity = _max_severity(usage_severity, corroborating_severity)
    top_process_text = (
        f"，最高进程 {top_process_name or '未知'} {top_process_cpu:.1f}%"
        if top_process_cpu is not None
        else ""
    )
    builder.finding(
        f"CPU 瞬时采样 {usage:.1f}%，1 分钟负载 {load_1m if load_1m is not None else '未知'}，"
        f"每核负载 {load_per_core if load_per_core is not None else '未知'}{top_process_text}。",
        severity,
    )
    if usage_severity in {"warning", "critical"} and severity == "notice":
        builder.recommend(
            "CPU 瞬时采样偏高，但每核负载和高占用进程未显示持续压力，建议间隔复测后再判断。"
        )
        builder.next("间隔 30 秒重新检查 CPU，并观察高占用进程是否持续。")
    elif severity in {"warning", "critical"}:
        builder.recommend("CPU 瞬时使用率与系统负载或高占用进程同时偏高，建议核对持续时间。")
        builder.next("查看高占用进程并结合服务日志确认来源。")
    else:
        builder.recommend("当前 CPU 瞬时采样与系统负载未见明显压力。")


def _disk(builder: DiagnosisBuilder, data: Any) -> None:
    rows = data if isinstance(data, list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mount = str(row.get("mounted_on") or row.get("mount") or "")
        if _is_virtual_disk_row(row, mount):
            continue
        usage = _percent_text(row.get("use_percent") or row.get("use"))
        builder.metric("disk_usage_percent", usage, "%", "disk_usage", context=mount)
        builder.metric("disk_available", row.get("available") or row.get("avail"), "", "disk_usage", context=mount)
        if usage is None:
            continue
        severity = _ascending_severity(usage, THRESHOLDS["disk_usage"])
        builder.finding(f"挂载点 {mount or '未知'} 的磁盘使用率为 {usage:.1f}%。", severity)
        if severity in {"warning", "critical"}:
            builder.recommend(f"挂载点 {mount or '未知'} 空间紧张，建议先检查大文件和日志增长。")
            builder.next(f"扫描 {mount or '目标挂载点'} 中的高占用文件，但不要直接删除。")
    if rows and not builder.findings:
        builder.finding("已读取磁盘使用情况，但部分文件系统未返回可解析的使用率。", "unknown")


def _is_virtual_disk_row(row: dict[str, Any], mount: str) -> bool:
    if mount in {"/", "/boot", "/boot/efi", "/tmp", "/home", "/var", "/var/log"}:
        return False
    filesystem = str(row.get("filesystem") or "").lower()
    if filesystem in {
        "tmpfs",
        "devtmpfs",
        "proc",
        "sysfs",
        "cgroup",
        "cgroup2",
        "efivarfs",
        "securityfs",
        "debugfs",
        "tracefs",
        "pstore",
        "configfs",
        "fusectl",
        "mqueue",
    }:
        return True
    return any(
        mount == prefix or mount.startswith(f"{prefix}/")
        for prefix in ("/dev", "/proc", "/sys", "/run")
    )


def _processes(builder: DiagnosisBuilder, data: Any) -> None:
    rows = data if isinstance(data, list) else []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        pid = row.get("pid")
        name = row.get("command") or row.get("name")
        cpu = _number(row.get("cpu"))
        mem = _number(row.get("mem"))
        builder.metric("process_cpu_percent", cpu, "%", "process_list", context=f"{pid}:{name}")
        builder.metric("process_memory_percent", mem, "%", "process_list", context=f"{pid}:{name}")
    top = next((row for row in rows if isinstance(row, dict)), None)
    if top:
        cpu = _number(top.get("cpu"))
        severity = _ascending_severity(cpu, THRESHOLDS["process_cpu"])
        builder.finding(
            f"当前 CPU 占用最高的进程为 {top.get('command') or top.get('name') or '未知'}"
            f"（PID {top.get('pid', '未知')}，CPU {_format_percent(cpu)}）。",
            severity,
        )
        if severity in {"warning", "critical"}:
            builder.recommend("建议核对该进程所属服务、启动时间和近期日志。")


def _network(builder: DiagnosisBuilder, data: Any) -> None:
    rows = data if isinstance(data, list) else []
    builder.metric("network_listener_count", len(rows), "listeners", "network_status")
    builder.finding(f"当前发现 {len(rows)} 条网络监听记录。", "normal" if rows else "notice")
    if not rows:
        builder.recommend("未发现监听记录时，请确认网络查询命令权限和系统环境。")


def _port(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    port = data.get("port")
    listeners = data.get("listeners") if isinstance(data.get("listeners"), list) else []
    builder.metric("port_listener_count", len(listeners), "listeners", "get_port_usage", context=str(port))
    if listeners:
        processes = sorted({str(item.get("process")) for item in listeners if isinstance(item, dict) and item.get("process")})
        suffix = f"，关联进程：{'、'.join(processes)}" if processes else ""
        builder.finding(f"端口 {port} 当前已被监听{suffix}。", "notice")
        builder.recommend("如该监听不符合预期，请核对进程归属与服务配置，不要直接终止进程。")
    else:
        builder.finding(f"端口 {port} 当前未发现监听进程。", "normal")


def _service(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    name = str(data.get("service_name") or "未知服务")
    state = str(data.get("active_state") or "unknown").lower()
    builder.metric("service_active_state", state, "", "get_service_status", context=name)
    if state == "active":
        builder.finding(f"服务 {name} 当前处于 active 状态。", "normal")
    elif state == "failed":
        builder.finding(f"服务 {name} 当前处于 failed 状态。", "critical")
        builder.recommend("建议查看该服务日志和退出原因，再由管理员决定是否重启。")
        builder.next(f"查询 {name} 的近期 journal 日志。")
    elif state in {"inactive", "deactivating"}:
        builder.finding(f"服务 {name} 当前处于 {state} 状态。", "warning")
        builder.recommend("请确认该服务是否应当运行，并查看停止原因。")
    else:
        builder.finding(f"服务 {name} 状态为 {state or 'unknown'}。", "unknown")


def _journal(builder: DiagnosisBuilder, data: Any) -> None:
    rows = data if isinstance(data, list) else []
    error_count = 0
    critical_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "")
        lowered = content.lower()
        if "critical" in lowered or "emerg" in lowered or "panic" in lowered:
            critical_count += 1
        elif "error" in lowered or "failed" in lowered:
            error_count += 1
    builder.metric("journal_entry_count", len(rows), "lines", "journal_query")
    builder.metric("journal_error_count", error_count, "lines", "journal_query")
    builder.metric("journal_critical_count", critical_count, "lines", "journal_query")
    if critical_count:
        builder.finding(f"近期日志中发现 {critical_count} 条 critical/emergency 级别线索。", "critical")
        builder.recommend("优先核对 critical 日志对应的服务、时间和上下文。")
    elif error_count:
        builder.finding(f"近期日志中发现 {error_count} 条 error/failed 线索。", "warning")
        builder.recommend("建议按服务和时间范围缩小日志查询。")
    else:
        builder.finding(f"已检查 {len(rows)} 条近期日志，未识别到 error/critical 关键词。", "normal")


def _large_files(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    files = data.get("files") if isinstance(data.get("files"), list) else []
    builder.metric("large_file_count", len(files), "files", "large_file_scan")
    builder.metric("large_file_scanned_count", data.get("scanned_files"), "files", "large_file_scan")
    if files:
        largest = files[0] if isinstance(files[0], dict) else {}
        builder.finding(
            f"发现 {len(files)} 个大文件候选，最大项为 {largest.get('path', '未知路径')}"
            f"（{largest.get('size', '大小未知')}）。",
            "notice",
        )
        builder.recommend("请先确认文件归属、保留策略和备份状态，不要直接删除。")
        builder.next("如需处置临时文件，请生成安全清理 dry-run 计划。")
    else:
        builder.finding("本次扫描未发现达到阈值的大文件候选。", "normal")


def _cleanup_scan(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    count = _number(data.get("candidate_count")) or 0
    total = _number(data.get("total_bytes")) or 0
    builder.metric("cleanup_candidate_count", int(count), "files", "safe_cleanup_scan")
    builder.metric("cleanup_candidate_bytes", int(total), "bytes", "safe_cleanup_scan")
    builder.finding(f"安全清理扫描发现 {int(count)} 个候选文件，总计 {_format_bytes(total)}。", "notice" if count else "normal")
    if count:
        builder.next("生成 dry-run 清理计划，核对每个候选文件后再决定是否隔离。")


def _cleanup_plan(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    count = _number(data.get("candidate_count")) or 0
    total = _number(data.get("total_bytes")) or 0
    builder.metric("cleanup_plan_file_count", int(count), "files", "safe_cleanup_plan")
    builder.metric("cleanup_plan_bytes", int(total), "bytes", "safe_cleanup_plan")
    builder.finding(
        f"已生成 dry-run 清理计划，包含 {int(count)} 个文件，总计 {_format_bytes(total)}；尚未移动文件。",
        "notice" if count else "normal",
    )
    if count:
        builder.recommend("请核对候选路径、大小和修改时间，再通过一次性确认执行隔离。")


def _cleanup_quarantine(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    moved = _number(data.get("moved_count")) or 0
    builder.metric("cleanup_quarantined_count", int(moved), "files", "safe_cleanup_quarantine")
    builder.finding(f"已将 {int(moved)} 个文件移入受控隔离区，未执行永久删除。", "notice")
    builder.next("如验证后需要撤销，可使用隔离编号执行受控恢复。")


def _cleanup_restore(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    restored = _number(data.get("restored_count")) or 0
    builder.metric("cleanup_restored_count", int(restored), "files", "safe_cleanup_restore")
    builder.finding(f"已从受控隔离区恢复 {int(restored)} 个文件。", "normal")


def _config_drift(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    action = str(data.get("action", ""))
    drift_count = _number(data.get("drift_count")) or 0
    critical_count = _number(data.get("critical_drift_count")) or 0
    present_count = _number(data.get("present_count")) or 0
    builder.metric("config_present_count", int(present_count), "files", "config_drift_check")
    builder.metric("config_drift_count", int(drift_count), "items", "config_drift_check")
    builder.metric("config_critical_drift_count", int(critical_count), "items", "config_drift_check")

    if action == "baseline_saved":
        builder.finding(f"已将当前 {int(present_count)} 个关键配置文件指纹保存为基线。", "normal")
        builder.recommend("后续 config_drift_check 将以此为基准检测漂移。")
        return
    if action == "collect_only":
        builder.finding(f"已采集 {int(present_count)} 个关键配置文件指纹，但未找到基线，无法做漂移对比。", "notice")
        builder.recommend("建议先以 save_baseline=1 建立基线，再执行漂移检测。")
        return
    if drift_count == 0:
        builder.finding(f"已对比基线，{int(present_count)} 个关键配置文件未发现漂移。", "normal")
        return
    severity = "critical" if critical_count else "warning"
    builder.finding(
        f"配置漂移检测发现 {int(drift_count)} 项漂移，其中 {int(critical_count)} 项为敏感配置关键漂移。",
        severity,
    )
    drift_items = data.get("drift_items") if isinstance(data.get("drift_items"), list) else []
    for item in drift_items[:5]:
        if not isinstance(item, dict):
            continue
        path = item.get("path", "未知路径")
        note = item.get("note", "")
        builder.finding(f"{path}：{note}", item.get("severity", "warning"))
    if critical_count:
        builder.recommend("敏感配置（sudoers/sshd_config/passwd）内容已变更，建议立即核对是否为授权变更。")
        builder.next("对比变更前后的配置内容，必要时回滚到基线版本。")
    else:
        builder.recommend("核对非敏感配置的漂移项，确认是否为预期维护变更。")


def _zombie_process(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    count = _number(data.get("zombie_count")) or 0
    builder.metric("zombie_process_count", int(count), "processes", "zombie_process_check")
    parents = data.get("parents") if isinstance(data.get("parents"), list) else []
    if count == 0:
        builder.finding("未发现僵尸进程，进程回收状态正常。", "normal")
        return
    severity = "warning" if count < 10 else "critical"
    builder.finding(f"检测到 {int(count)} 个僵尸进程，需要父进程 reap 或重启父服务。", severity)
    parent_names = sorted({str(p.get("comm", "")) for p in parents if isinstance(p, dict) and p.get("comm")})
    if parent_names:
        builder.finding(f"产生僵尸的父进程：{', '.join(parent_names[:5])}", severity)
    builder.recommend(str(data.get("recommendation", "重启产生僵尸的父服务以 reap 子进程。")))
    builder.next("核对父服务代码的子进程回收逻辑，或受控重启父服务。")


def _disk_io(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    device_count = _number(data.get("device_count")) or 0
    bottleneck_count = _number(data.get("bottleneck_count")) or 0
    builder.metric("disk_io_device_count", int(device_count), "devices", "disk_io_analysis")
    builder.metric("disk_io_bottleneck_count", int(bottleneck_count), "devices", "disk_io_analysis")
    bottlenecks = data.get("bottlenecks") if isinstance(data.get("bottlenecks"), list) else []
    if bottleneck_count == 0:
        builder.finding(f"已检查 {int(device_count)} 个块设备，未发现 I/O 瓶颈。", "normal")
        return
    severity = "warning" if bottleneck_count < 3 else "critical"
    builder.finding(f"检测到 {int(bottleneck_count)} 个 I/O 瓶颈设备。", severity)
    for dev in bottlenecks[:3]:
        if not isinstance(dev, dict):
            continue
        name = dev.get("device", "未知")
        util = dev.get("util_percent", "未知")
        await_ms = dev.get("await_ms", dev.get("r_await_ms", "未知"))
        builder.finding(f"{name}: util={util}%, await={await_ms}ms", severity)
    builder.recommend(str(data.get("recommendation", "结合 process_list 定位高 I/O 进程，不要直接终止。")))
    builder.next("调用 process_list 和 large_file_scan 交叉定位 I/O 来源。")


def _impact(builder: DiagnosisBuilder, data: Any) -> None:
    if not isinstance(data, dict):
        return
    path = str(data.get("path", "未知路径"))
    holder_count = int(_number(data.get("holder_count")) or 0)
    builder.metric("impact_holder_count", holder_count, "processes", "impact_analysis")
    builder.metric(
        "impact_affected_services",
        len(data.get("affected_services") or []),
        "services",
        "impact_analysis",
    )

    if not data.get("exists"):
        builder.finding(f"{path} 不存在，无影响面。", "normal")
        return

    severity = str(data.get("severity", "info"))
    mapped = {"critical": "critical", "warning": "warning"}.get(severity, "normal")

    if data.get("handle_leak_risk"):
        builder.finding(
            f"{path} 正被 {holder_count} 个进程持有句柄，直接删除不会释放磁盘空间。",
            mapped,
        )
    else:
        builder.finding(f"{path} 当前无进程持有句柄，影响面隔离。", mapped)

    for warning in (data.get("warnings") or [])[:3]:
        builder.finding(str(warning), mapped)

    recommendation = str(data.get("recommendation", ""))
    if recommendation:
        builder.recommend(recommendation)

    safe_action = str(data.get("safe_action", ""))
    if safe_action == "truncate_or_logrotate":
        builder.next("使用 truncate 或配置 logrotate copytruncate，不要直接 rm。")
    elif safe_action == "safe_to_remove":
        builder.next("可调用 safe_cleanup_plan 生成 dry-run 计划后人工确认。")
    else:
        builder.next("由管理员评估相关服务影响后再决定处置方式。")


def _unknown_summary(execution_status: str, hint: str) -> str:
    if hint:
        return hint
    if execution_status == "environment_limited":
        return "当前环境能力受限，未获得足够的真实设备数据形成诊断。"
    if execution_status == "failed":
        return "系统检查未获得有效结果，暂时无法形成可靠诊断。"
    if execution_status == "not_executed":
        return "本次请求未执行工具，暂无可用于诊断的设备数据。"
    return "暂未获得足够的真实工具数据形成诊断。"


def _summary_from_findings(findings: list[str], severity: str) -> str:
    if not findings:
        return "已获得工具数据，但暂无可总结的诊断发现。"
    prefix = {
        "normal": "系统检查未发现明显异常。",
        "notice": "系统检查发现需要关注的信息。",
        "warning": "系统检查发现需要尽快处理的异常。",
        "critical": "系统检查发现高优先级异常。",
    }.get(severity, "系统检查已完成。")
    return f"{prefix} {' '.join(findings[:2])}"


def _ascending_severity(value: float | None, thresholds: tuple[float, float, float]) -> str:
    if value is None:
        return "unknown"
    notice, warning, critical = thresholds
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    if value >= notice:
        return "notice"
    return "normal"


def _max_severity(*values: str) -> str:
    return max(values, key=lambda value: SEVERITY_ORDER.get(value, 0))


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * 100, 1)


def _percent_text(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.strip().rstrip("%")
    return _number(value)


def _format_percent(value: float | None) -> str:
    return "未知" if value is None else f"{value:.1f}%"


def _format_mb(value: float | None) -> str:
    if value is None:
        return "未知"
    if value >= 1024:
        return f"{value / 1024:.1f} GB"
    return f"{value:.0f} MB"


def _format_bytes(value: float) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value:.0f} B"
