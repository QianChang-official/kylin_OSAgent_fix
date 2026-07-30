"""Change event timeline for change-induced failure correlation.

Most production incidents are triggered by a change, not by spontaneous
degradation. Detecting drift is only half the job — knowing *when* it
happened is what lets the root cause engine answer "which change caused
this failure?".

Every drift detection is appended here with a timestamp, so a later
service failure can be correlated against recent configuration changes.
Storage is an append-only JSONL file under data/ (no extra dependency,
survives restarts, trivially inspectable during a demo).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any

from backend import config

CHANGE_LOG_PATH = config.PROJECT_DIR / "data" / "change_events.jsonl"
MAX_EVENTS = 2000

# Config path fragment -> service name. Used to link a changed file to the
# service it configures, which is what makes the correlation meaningful.
CONFIG_SERVICE_MAP = {
    "sshd_config": "sshd",
    "ssh_config": "sshd",
    "nginx": "nginx",
    "httpd": "httpd",
    "apache2": "apache2",
    "my.cnf": "mysqld",
    "mysqld": "mysqld",
    "postgresql": "postgresql",
    "redis": "redis",
    "docker": "docker",
    "chrony": "chronyd",
    "ntp": "ntpd",
    "resolv.conf": "systemd-resolved",
    "fstab": "mount",
    "crontab": "crond",
    "sysctl.conf": "kernel",
    "limits.conf": "kernel",
    "passwd": "system-auth",
    "group": "system-auth",
    "sudoers": "sudo",
    "hosts": "network",
}


class ChangeLog:
    def __init__(self, path: Path | None = None, max_events: int = MAX_EVENTS) -> None:
        self.path = path or CHANGE_LOG_PATH
        self.max_events = max_events
        self._lock = Lock()

    def record(self, drift_items: list[dict[str, Any]], source: str = "config_drift_check",
               detected_at: float | None = None) -> int:
        """Append drift items to the timeline. Returns the number recorded."""
        if not drift_items:
            return 0
        stamp = time.time() if detected_at is None else detected_at
        events = []
        for item in drift_items:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", ""))
            events.append({
                "detected_at": stamp,
                "source": source,
                "path": path,
                "change": item.get("change"),
                "severity": item.get("severity", "warning"),
                "note": item.get("note", ""),
                "affected_service": infer_service(path),
            })
        if not events:
            return 0

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                for event in events:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._trim_locked()
        return len(events)

    def recent(self, within_seconds: float | None = None, now: float | None = None) -> list[dict[str, Any]]:
        """Change events, newest first, optionally limited to a time window."""
        events = self._read()
        if within_seconds is not None:
            current = time.time() if now is None else now
            events = [
                event for event in events
                if current - float(event.get("detected_at", 0)) <= within_seconds
            ]
        events.sort(key=lambda item: float(item.get("detected_at", 0)), reverse=True)
        return events

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        events: list[dict[str, Any]] = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    events.append(record)
        except OSError:
            return []
        return events

    def _trim_locked(self) -> None:
        events = self._read()
        if len(events) <= self.max_events:
            return
        keep = events[-self.max_events:]
        with self.path.open("w", encoding="utf-8", newline="\n") as handle:
            for event in keep:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def infer_service(path: str) -> str:
    """Map a configuration file to the service it configures."""
    lowered = (path or "").lower()
    for fragment, service in CONFIG_SERVICE_MAP.items():
        if fragment in lowered:
            return service
    return ""


_change_log: ChangeLog | None = None


def get_change_log() -> ChangeLog:
    global _change_log
    if _change_log is None:
        _change_log = ChangeLog()
    return _change_log
