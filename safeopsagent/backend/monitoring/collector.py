"""Lightweight metric collection for the monitoring dashboard.

This is deliberately separate from the tool layer: tools shell out through
SafeExecutor and are meant for on-demand diagnosis, while this collector
runs on a short interval and must stay cheap. It reads /proc directly on
Linux (the Kylin target) and falls back to Win32 counters on Windows so
the dashboard is demonstrable on a development machine.

Unavailable metrics are reported as None rather than zero — a missing
metric and a metric that is genuinely zero must not look the same.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROC_STAT = Path("/proc/stat")
PROC_MEMINFO = Path("/proc/meminfo")
PROC_LOADAVG = Path("/proc/loadavg")
PROC_UPTIME = Path("/proc/uptime")

# Metrics tracked by the baseline engine. Order drives dashboard display.
TRACKED_METRICS = (
    "cpu_percent",
    "mem_percent",
    "swap_percent",
    "disk_percent",
    "load_per_core",
)

METRIC_LABELS = {
    "cpu_percent": "CPU 使用率",
    "mem_percent": "内存使用率",
    "swap_percent": "Swap 使用率",
    "disk_percent": "根分区使用率",
    "load_per_core": "单核负载",
}

METRIC_UNITS = {
    "cpu_percent": "%",
    "mem_percent": "%",
    "swap_percent": "%",
    "disk_percent": "%",
    "load_per_core": "",
}


@dataclass
class MetricSample:
    """One point in time across all tracked metrics."""

    ts: float
    values: dict[str, float | None] = field(default_factory=dict)
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "source": self.source, **self.values}


class MetricCollector:
    """Stateful collector — CPU needs the delta between two samples."""

    def __init__(self) -> None:
        self._prev_cpu: tuple[int, int] | None = None
        self._prev_win_cpu: tuple[int, int] | None = None

    def collect(self) -> MetricSample:
        if PROC_STAT.is_file():
            return self._collect_linux()
        if sys.platform == "win32":
            return self._collect_windows()
        return MetricSample(ts=time.time(), values={m: None for m in TRACKED_METRICS}, source="unsupported")

    # ---------- Linux (Kylin target) ----------

    def _collect_linux(self) -> MetricSample:
        values: dict[str, float | None] = {metric: None for metric in TRACKED_METRICS}
        values["cpu_percent"] = self._linux_cpu_percent()

        mem_total, mem_available, swap_total, swap_free = self._linux_meminfo()
        if mem_total:
            used = mem_total - (mem_available if mem_available is not None else 0)
            values["mem_percent"] = round(used / mem_total * 100, 1)
        if swap_total:
            values["swap_percent"] = round((swap_total - (swap_free or 0)) / swap_total * 100, 1)
        elif swap_total == 0:
            values["swap_percent"] = 0.0

        values["disk_percent"] = self._disk_percent("/")

        try:
            load_1m = float(PROC_LOADAVG.read_text(encoding="utf-8").split()[0])
            cores = os.cpu_count() or 1
            values["load_per_core"] = round(load_1m / cores, 3)
        except (OSError, ValueError, IndexError):
            pass

        return MetricSample(ts=time.time(), values=values, source="/proc")

    def _linux_cpu_percent(self) -> float | None:
        try:
            line = next(
                item for item in PROC_STAT.read_text(encoding="utf-8").splitlines()
                if item.startswith("cpu ")
            )
        except (OSError, StopIteration):
            return None
        parts = [int(value) for value in line.split()[1:]]
        if len(parts) < 5:
            return None
        total = sum(parts[:8])
        idle = parts[3] + parts[4]
        previous, self._prev_cpu = self._prev_cpu, (total, idle)
        if previous is None:
            return None  # first sample establishes the baseline delta
        total_delta = total - previous[0]
        idle_delta = idle - previous[1]
        if total_delta <= 0:
            return None
        return round(max(0.0, min(100.0, (total_delta - idle_delta) / total_delta * 100)), 1)

    def _linux_meminfo(self) -> tuple[int | None, int | None, int | None, int | None]:
        try:
            text = PROC_MEMINFO.read_text(encoding="utf-8")
        except OSError:
            return None, None, None, None
        fields: dict[str, int] = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            try:
                fields[key.strip()] = int(raw.split()[0])
            except (ValueError, IndexError):
                continue
        return (
            fields.get("MemTotal"),
            fields.get("MemAvailable"),
            fields.get("SwapTotal"),
            fields.get("SwapFree"),
        )

    # ---------- Windows (development fallback) ----------

    def _collect_windows(self) -> MetricSample:
        values: dict[str, float | None] = {metric: None for metric in TRACKED_METRICS}
        values["cpu_percent"] = self._windows_cpu_percent()
        values["mem_percent"] = self._windows_mem_percent()
        values["disk_percent"] = self._disk_percent(os.environ.get("SystemDrive", "C:") + "\\")
        # Windows has no load average or swap semantics comparable to Linux.
        return MetricSample(ts=time.time(), values=values, source="win32")

    def _windows_cpu_percent(self) -> float | None:
        try:
            import ctypes
            from ctypes import wintypes

            class _FileTime(ctypes.Structure):
                _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

            def as_int(ft: "_FileTime") -> int:
                return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

            idle, kernel, user = _FileTime(), _FileTime(), _FileTime()
            if not ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            ):
                return None
            total = as_int(kernel) + as_int(user)
            idle_total = as_int(idle)
        except Exception:
            return None

        previous, self._prev_win_cpu = self._prev_win_cpu, (total, idle_total)
        if previous is None:
            return None
        total_delta = total - previous[0]
        idle_delta = idle_total - previous[1]
        if total_delta <= 0:
            return None
        return round(max(0.0, min(100.0, (total_delta - idle_delta) / total_delta * 100)), 1)

    def _windows_mem_percent(self) -> float | None:
        try:
            import ctypes
            from ctypes import wintypes

            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return float(status.dwMemoryLoad)
        except Exception:
            return None

    # ---------- shared ----------

    def _disk_percent(self, mount: str) -> float | None:
        try:
            usage = shutil.disk_usage(mount)
        except OSError:
            return None
        if usage.total <= 0:
            return None
        return round(usage.used / usage.total * 100, 1)


def host_overview() -> dict[str, Any]:
    """Static host facts for the dashboard header."""
    import platform

    overview: dict[str, Any] = {
        "hostname": platform.node(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "logical_cores": os.cpu_count(),
        "uptime_seconds": None,
        "boot_time": None,
    }
    try:
        uptime = float(PROC_UPTIME.read_text(encoding="utf-8").split()[0])
        overview["uptime_seconds"] = int(uptime)
        overview["boot_time"] = int(time.time() - uptime)
    except (OSError, ValueError, IndexError):
        pass
    try:
        os_release = Path("/etc/os-release").read_text(encoding="utf-8")
        for line in os_release.splitlines():
            if line.startswith("PRETTY_NAME="):
                overview["os_release"] = line.split("=", 1)[1].strip().strip('"')
                break
    except OSError:
        pass
    return overview
