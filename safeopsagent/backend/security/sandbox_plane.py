"""Synthetic data plane for deception (sandbox) sessions.

A sandboxed client is served this module's output instead of the real handlers.
Nothing here reads the host, the audit database, the tool registry or any
configuration: every value is fabricated from a seed derived from the sandbox
session id. That makes the deception self-consistent across requests — the same
intruder sees the same fake host, the same fake services — while guaranteeing by
construction that no real datum can leak through.

Response shapes mirror the genuine API so the console renders normally. The
fabricated environment is deliberately mundane: a mid-sized application server
with unremarkable load. It contains no real hostnames, addresses, or credentials,
and the "findings" it reports are inert strings.
"""
from __future__ import annotations

import hashlib
import random
import time
from typing import Any, Mapping, Optional

SANDBOX_USERNAME = "opsadmin"

# Fabricated inventory. Chosen to look like an ordinary Kylin application host
# so the environment invites exploration without implying anything real.
_SERVICE_POOL = (
    ("nginx.service", "running", "Web 反向代理"),
    ("mysqld.service", "running", "业务数据库"),
    ("redis.service", "running", "缓存服务"),
    ("app-gateway.service", "running", "业务网关"),
    ("node-exporter.service", "running", "指标采集"),
    ("logrotate.timer", "waiting", "日志轮转"),
    ("backup-agent.service", "failed", "备份代理"),
)

_MOUNT_POOL = (
    ("/", "/dev/vda1", "ext4"),
    ("/var", "/dev/vda2", "ext4"),
    ("/data", "/dev/vdb1", "xfs"),
)

_PROCESS_POOL = (
    ("nginx", "www-data"),
    ("mysqld", "mysql"),
    ("redis-server", "redis"),
    ("java", "appuser"),
    ("python3", "appuser"),
    ("node-exporter", "prometheus"),
)

_METRIC_KEYS = (
    "cpu_percent",
    "mem_percent",
    "swap_percent",
    "disk_percent",
    "load_per_core",
)

_METRIC_LABELS = {
    "cpu_percent": "CPU 使用率",
    "mem_percent": "内存使用率",
    "swap_percent": "Swap 使用率",
    "disk_percent": "根分区使用率",
    "load_per_core": "单核负载",
}

_METRIC_UNITS = {
    "cpu_percent": "%",
    "mem_percent": "%",
    "swap_percent": "%",
    "disk_percent": "%",
    "load_per_core": "",
}

_METRIC_CENTERS = {
    "cpu_percent": 24.0,
    "mem_percent": 61.0,
    "swap_percent": 3.0,
    "disk_percent": 68.0,
    "load_per_core": 0.42,
}

# Tool catalogue advertised inside the sandbox. Names match the real read-only
# tools so the surface looks authentic, but calling one only ever returns
# fabricated output — the registry is never consulted.
_TOOL_CATALOG = (
    ("disk_usage", "查看磁盘分区使用率"),
    ("process_list", "列出占用资源最高的进程"),
    ("memory_status", "查看内存与 Swap 使用情况"),
    ("cpu_status", "查看 CPU 负载与使用率"),
    ("network_status", "查看网络连接与监听端口"),
    ("service_status", "查询 systemd 服务状态"),
    ("journal_query", "检索系统日志"),
    ("port_check", "检查端口占用"),
    ("large_file_scan", "扫描大文件"),
)


def _seed_of(sandbox_id: str) -> int:
    digest = hashlib.sha256(f"safeops.sandbox.{sandbox_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class Fabricator:
    """Deterministic generator of a single sandbox's fake environment."""

    def __init__(self, sandbox_id: str) -> None:
        self.sandbox_id = str(sandbox_id)
        self._random = random.Random(_seed_of(self.sandbox_id))
        self.hostname = self._hostname()
        self.services = self._pick_services()
        self.boot_time = time.time() - self._random.uniform(6 * 86_400, 45 * 86_400)

    def _hostname(self) -> str:
        from backend import config

        configured = str(getattr(config, "HONEYPOT_HOSTNAME", "") or "").strip()
        if configured:
            return configured
        return f"kylin-app-{self._random.randint(2, 19):02d}"

    def _pick_services(self) -> tuple[tuple[str, str, str], ...]:
        pool = list(_SERVICE_POOL)
        self._random.shuffle(pool)
        return tuple(pool[:6])

    # ------------------------------------------------------------- primitives

    def _jitter(self, metric: str, at: float, variant: str = "") -> float:
        """Smooth pseudo-random walk so a series looks sampled, not random.

        ``variant`` separates values that share a metric but not a subject —
        three mount points must not report an identical usage figure.
        """
        center = _METRIC_CENTERS[metric]
        span = center * 0.18 if metric != "load_per_core" else 0.16
        # Derive from the timestamp bucket so repeated reads agree with history.
        bucket = int(at // 30)
        local = random.Random(_seed_of(f"{self.sandbox_id}:{metric}:{variant}:{bucket}"))
        offset = local.uniform(-span, span)
        if variant:
            # A stable per-subject shift, so each mount keeps its own level
            # across samples instead of drifting independently every read.
            steady = random.Random(_seed_of(f"{self.sandbox_id}:{metric}:{variant}"))
            offset += steady.uniform(-center * 0.22, center * 0.22)
        value = center + offset
        if metric == "load_per_core":
            return round(max(0.02, value), 2)
        return round(min(99.0, max(0.4, value)), 1)

    def metric_series(self, metric: str, points: int) -> dict[str, Any]:
        now = time.time()
        bounded = max(2, min(int(points), 400))
        step = 30.0
        series = [
            {
                "ts": round(now - (bounded - index - 1) * step, 3),
                "value": self._jitter(metric, now - (bounded - index - 1) * step),
            }
            for index in range(bounded)
        ]
        values = [item["value"] for item in series]
        median = round(sum(values) / len(values), 2)
        deviations = sorted(abs(value - median) for value in values)
        mad = round(deviations[len(deviations) // 2], 3) or 0.5
        return {
            "label": _METRIC_LABELS[metric],
            "unit": _METRIC_UNITS[metric],
            "points": series,
            "latest": values[-1],
            "baseline": {
                "metric": metric,
                "median": median,
                "mad": mad,
                "sample_count": len(values),
                "normal_lower": round(median - 3 * mad, 2),
                "normal_upper": round(median + 3 * mad, 2),
                "learned": True,
            },
            "available": True,
            "sample_count": len(values),
        }

    # --------------------------------------------------------------- payloads

    def agent_status(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent_mode": "offline_safe",
            "model_provider": "offline_safe",
            "model_vendor": "内置",
            "model_name": "offline-safe-planner",
            "planner_source": "offline_safe",
            "guardrail_enabled": True,
            "risk_scoring_enabled": True,
            "audit_enabled": True,
            "tools_count": len(_TOOL_CATALOG),
            "readonly_tools_count": len(_TOOL_CATALOG),
            "security_summary": "只读工具可用，处置类操作需人工确认。",
            "deployment_hint": f"{self.hostname} · 生产应用节点",
        }

    def system_probe(self) -> dict[str, Any]:
        return {
            "kernel": "5.10.0-9-generic",
            "os_release": "Kylin Linux Advanced Server V10 (Halberd)",
            "python_version": "3.11.6",
            "available_commands": ["ps", "df", "free", "ss", "systemctl", "journalctl", "du", "find"],
            "missing_commands": ["iostat", "lsof"],
        }

    def tools_list(self) -> dict[str, Any]:
        return {
            "tools": [
                {
                    "name": name,
                    "description": description,
                    "inputSchema": {"type": "object", "properties": {}, "required": []},
                }
                for name, description in _TOOL_CATALOG
            ]
        }

    def host_overview(self) -> dict[str, Any]:
        return {
            "hostname": self.hostname,
            "system": "Linux",
            "release": "5.10.0-9-generic",
            "machine": "loongarch64",
            "python_version": "3.11.6",
            "logical_cores": 8,
            "uptime_seconds": round(time.time() - self.boot_time, 1),
            "boot_time": round(self.boot_time, 1),
            "os_release": "Kylin Linux Advanced Server V10 (Halberd)",
        }

    def monitor_overview(self) -> dict[str, Any]:
        return {
            "host": self.host_overview(),
            "health": "healthy",
            "anomaly_count": 0,
            "sample_count": 1440,
            "sampler_running": True,
            "sample_interval_seconds": 30.0,
            "collector_source": "procfs",
        }

    def monitor_metrics(self, points: int) -> dict[str, Any]:
        return {
            "metrics": {metric: self.metric_series(metric, points) for metric in _METRIC_KEYS},
            "tracked": list(_METRIC_KEYS),
            "sample_count": 1440,
            "sampler_running": True,
            "sample_interval_seconds": 30.0,
            "collector_source": "procfs",
        }

    def audit_logs(self, limit: int) -> dict[str, Any]:
        """Fabricated history. Real audit rows are never read for a sandbox."""
        bounded = max(1, min(int(limit), 100))
        now = time.time()
        samples = (
            ("查看磁盘使用率", "disk_usage", "allow", "completed", 12),
            ("检查内存状态", "memory_status", "allow", "completed", 10),
            ("查询 nginx 服务状态", "service_status", "allow", "completed", 14),
            ("列出高负载进程", "process_list", "allow", "completed", 11),
            ("检索最近告警日志", "journal_query", "allow", "completed", 16),
            ("清理临时目录", "cleanup_plan", "confirm", "awaiting_confirmation", 46),
        )
        logs = []
        for index in range(bounded):
            prompt, tool, decision, status, score = samples[index % len(samples)]
            stamp = now - (index + 1) * 420
            logs.append(
                {
                    "id": 4820 - index,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp)),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp)),
                    "request_id": hashlib.sha256(
                        f"{self.sandbox_id}:audit:{index}".encode("utf-8")
                    ).hexdigest()[:8],
                    "session_id": f"ops-{self.sandbox_id[:6]}",
                    "user_input": prompt,
                    "intent": "readonly_query",
                    "agent_mode": "offline_safe",
                    "selected_tool": tool,
                    "risk_score": score,
                    "risk_band": "low" if score < 40 else "medium",
                    "risk_level_text": "low" if score < 40 else "medium",
                    "security_decision": decision,
                    "security_reason": "只读工具，允许执行。" if decision == "allow" else "需人工确认。",
                    "execution_status": status,
                    "executed": decision == "allow",
                    "summary": f"{prompt} 已完成。",
                    "rule_labels": [],
                }
            )
        return {"logs": logs}

    def audit_trace(self, request_id: str) -> dict[str, Any]:
        return {
            "found": True,
            "request_id": str(request_id)[:64],
            "audit": self.audit_logs(1)["logs"][0],
            "trace": {"events": []},
            "timeline": [
                {"title": "安全预检", "status": "done", "description": "未命中危险规则。"},
                {"title": "工具规划", "status": "done", "description": "选择只读工具。"},
                {"title": "执行", "status": "done", "description": "命令执行完成。"},
                {"title": "审计", "status": "done", "description": "已写入审计记录。"},
            ],
        }

    def chat(self, message: str, session_id: str) -> dict[str, Any]:
        request_id = hashlib.sha256(
            f"{self.sandbox_id}:chat:{message}".encode("utf-8")
        ).hexdigest()[:8]
        return {
            "response": (
                f"{self.hostname} 当前运行正常。CPU 与内存均在基线区间内，"
                "未发现需要立即处置的异常。"
            ),
            "summary": "系统状态正常，无需处置。",
            "intent": "readonly_query",
            "request_id": request_id,
            "session_id": str(session_id)[:64],
            "risk_score": 12,
            "risk_level": "low",
            "risk_band": "low",
            "security_decision": "allow",
            "security_reason": "只读查询，允许执行。",
            "execution_status": "completed",
            "executed": True,
            "agent_mode": "offline_safe",
            "model_provider": "offline_safe",
            "planner_source": "offline_safe",
            "confirmation_required": False,
            "confirmation_token": None,
            "matched_rules": [],
            "rule_labels": [],
            "tool_plan": [
                {
                    "tool_name": "memory_status",
                    "reason": "确认内存与 Swap 使用率",
                    "status": "completed",
                    "risk_score": 10,
                }
            ],
            "tool_results": [
                {
                    "tool": "memory_status",
                    "status": "success",
                    "data": {
                        "mem_percent": self._jitter("mem_percent", time.time()),
                        "swap_percent": self._jitter("swap_percent", time.time()),
                    },
                }
            ],
            "diagnosis": {
                "summary": "系统运行正常。",
                "severity": "normal",
                "findings": ["CPU、内存、磁盘均在学习基线区间内。"],
                "recommendations": ["保持当前监控频率。"],
                "next_actions": [],
                "evidence": [
                    {
                        "metric": "内存使用率",
                        "value": self._jitter("mem_percent", time.time()),
                        "unit": "%",
                        "source_tool": "memory_status",
                    }
                ],
            },
        }

    def tool_call(self, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        request_id = hashlib.sha256(
            f"{self.sandbox_id}:tool:{tool_name}".encode("utf-8")
        ).hexdigest()[:8]
        known = {name for name, _ in _TOOL_CATALOG}
        if str(tool_name) not in known:
            return {
                "success": False,
                "request_id": request_id,
                "tool_name": str(tool_name)[:64],
                "error": "工具不存在或未在白名单内。",
                "security_decision": "reject",
                "security_reason": "工具未注册。",
                "executed": False,
                "result": None,
            }
        return {
            "success": True,
            "request_id": request_id,
            "tool_name": str(tool_name)[:64],
            "arguments": dict(list(arguments.items())[:20]) if arguments else {},
            "risk_score": 12,
            "risk_level": "low",
            "risk_band": "low",
            "security_decision": "allow",
            "security_reason": "只读工具，允许执行。",
            "confirmation_required": False,
            "confirmation_token": None,
            "executed": True,
            "result": self._tool_result(str(tool_name)),
            "matched_rules": [],
            "rule_labels": [],
        }

    def _tool_result(self, tool_name: str) -> dict[str, Any]:
        now = time.time()
        if tool_name == "disk_usage":
            return {
                "tool": tool_name,
                "status": "success",
                "data": {
                    "partitions": [
                        {
                            "mount": mount,
                            "device": device,
                            "fstype": fstype,
                            "use_percent": self._jitter("disk_percent", now, mount),
                        }
                        for mount, device, fstype in _MOUNT_POOL
                    ]
                },
            }
        if tool_name == "process_list":
            return {
                "tool": tool_name,
                "status": "success",
                "data": {
                    "processes": [
                        {
                            "pid": 1000 + index * 137,
                            "user": user,
                            "command": command,
                            "cpu_percent": round(max(0.1, self._jitter("cpu_percent", now, command) / (index + 2)), 1),
                            "mem_percent": round(max(0.1, self._jitter("mem_percent", now, command) / (index + 3)), 1),
                        }
                        for index, (command, user) in enumerate(_PROCESS_POOL)
                    ]
                },
            }
        if tool_name == "service_status":
            return {
                "tool": tool_name,
                "status": "success",
                "data": {
                    "services": [
                        {"name": name, "state": state, "description": description}
                        for name, state, description in self.services
                    ]
                },
            }
        if tool_name == "memory_status":
            return {
                "tool": tool_name,
                "status": "success",
                "data": {
                    "mem_percent": self._jitter("mem_percent", now),
                    "swap_percent": self._jitter("swap_percent", now),
                    "total_mb": 16_384,
                },
            }
        if tool_name == "cpu_status":
            return {
                "tool": tool_name,
                "status": "success",
                "data": {
                    "cpu_percent": self._jitter("cpu_percent", now),
                    "load_per_core": self._jitter("load_per_core", now),
                    "logical_cores": 8,
                },
            }
        if tool_name == "network_status":
            return {
                "tool": tool_name,
                "status": "success",
                "data": {
                    "listening": [
                        {"port": 80, "process": "nginx"},
                        {"port": 443, "process": "nginx"},
                        {"port": 3306, "process": "mysqld"},
                        {"port": 6379, "process": "redis-server"},
                    ]
                },
            }
        if tool_name == "journal_query":
            return {
                "tool": tool_name,
                "status": "success",
                "data": {
                    "entries": [
                        {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "unit": "nginx.service", "message": "reload completed"},
                        {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "unit": "backup-agent.service", "message": "retry scheduled"},
                    ]
                },
            }
        if tool_name == "port_check":
            return {"tool": tool_name, "status": "success", "data": {"port": 80, "in_use": True, "process": "nginx"}}
        return {
            "tool": tool_name,
            "status": "success",
            "data": {"files": [], "note": "未发现超过阈值的大文件。"},
        }


_CACHE: dict[str, Fabricator] = {}
_CACHE_LIMIT = 256


def fabricator_for(sandbox_id: str) -> Fabricator:
    """Reuse one fabricator per sandbox so its environment stays stable."""
    key = str(sandbox_id)
    found = _CACHE.get(key)
    if found is None:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.clear()
        found = Fabricator(key)
        _CACHE[key] = found
    return found


def _int_param(query: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(str(query.get(name, default)))
    except (TypeError, ValueError):
        return default


def synthetic_response(
    sandbox_id: str,
    method: str,
    path: str,
    query: Optional[Mapping[str, str]] = None,
    body: Optional[Mapping[str, Any]] = None,
) -> tuple[int, dict[str, Any]]:
    """Return ``(status_code, payload)`` for a sandboxed request.

    Unknown routes yield a plausible 404 rather than an error that would betray
    the deception.
    """
    fake = fabricator_for(sandbox_id)
    verb = str(method).upper()
    route = str(path).rstrip("/") or "/"
    params = query or {}
    payload = body or {}

    if route == "/agent/status":
        return 200, fake.agent_status()
    if route == "/system/probe":
        return 200, fake.system_probe()
    if route == "/tools/list":
        return 200, fake.tools_list()
    if route == "/monitor/overview":
        return 200, fake.monitor_overview()
    if route == "/monitor/metrics":
        return 200, fake.monitor_metrics(_int_param(params, "points", 120))
    if route == "/monitor/anomalies":
        return 200, {"anomalies": []}
    if route == "/monitor/sample" and verb == "POST":
        return 200, {"sample": {"ts": time.time(), "source": "procfs"}, "stored_metrics": len(_METRIC_KEYS)}
    if route == "/audit/logs":
        return 200, fake.audit_logs(_int_param(params, "limit", 20))
    if route.startswith("/audit/trace/"):
        return 200, fake.audit_trace(route.rsplit("/", 1)[-1])
    if route == "/audit/clear" and verb == "POST":
        # Nothing is cleared; the real audit trail is append-only and unreachable.
        return 200, {"cleared": 0, "detail": "审计记录为追加写入，不可清除。"}
    if route == "/chat" and verb == "POST":
        return 200, fake.chat(str(payload.get("message", ""))[:500], str(payload.get("session_id", "")))
    if route == "/tools/call" and verb == "POST":
        arguments = payload.get("arguments")
        return 200, fake.tool_call(
            str(payload.get("tool_name", "")),
            arguments if isinstance(arguments, Mapping) else {},
        )
    if route == "/tools/confirm" and verb == "POST":
        return 200, {
            "success": False,
            "request_id": hashlib.sha256(f"{sandbox_id}:confirm".encode()).hexdigest()[:8],
            "tool_name": "",
            "error": "确认令牌已过期或不存在。",
            "executed": False,
            "result": None,
        }
    if route == "/security/resources":
        return 200, {
            "last_checked_at": "2026-07-30",
            "sources": [],
            "codex_security": {
                "id": "openai-codex-security",
                "source": "OpenAI",
                "title": "Codex Security",
                "url": "https://github.com/openai/codex-security",
                "package": "@openai/codex-security",
                "pinned_version": "0.1.4",
                "summary": "Isolated scan-host integration with read-only result import.",
                "commands": [],
                "safeops_usage": [],
            },
            "tool_categories": [],
            "articles": [],
            "project_applications": [],
            "policy": {
                "restricted_category_count": 0,
                "summary": "External material is treated as untrusted defensive reference.",
            },
        }
    if route == "/security/integrations":
        return 200, {"integrations": [], "external_content_policy": {}}
    if route == "/security/intel/aisecurity":
        return 200, {
            "source": {"name": "AI Security feed", "feed_url": ""},
            "untrusted": True,
            "automatic_model_ingestion": False,
            "mapping_mode": "deterministic_local_keywords",
            "item_count": 0,
            "items": [],
            "delivery": "local_snapshot",
            "snapshot_used": True,
        }
    if route.startswith("/security/codex/scans"):
        return 200, {"scans": [], "configured": False, "results_dir": ""}

    return 404, {"detail": "Not Found"}
