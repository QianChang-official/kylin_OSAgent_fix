"""Tool: config_drift_check - detect critical config file drift.

Competition scenario explicitly names "configuration file drift". This
tool collects read-only fingerprints (sha256 + mode + owner + mtime) for
a whitelist of critical config files and compares them against a stored
baseline to surface drift: added / deleted / content modified / mode
changed / owner changed.

Fingerprint collection uses Python standard library only (hashlib +
os.stat), which is read-only and does not shell out, so it is safe and
cross-platform testable.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .registry import ToolSchema, ToolResult, get_registry


CRITICAL_CONFIG_PATHS = [
    "/etc/ssh/sshd_config",
    "/etc/hosts",
    "/etc/passwd",
    "/etc/group",
    "/etc/sudoers",
    "/etc/crontab",
    "/etc/fstab",
    "/etc/resolv.conf",
    "/etc/sysctl.conf",
    "/etc/security/limits.conf",
]

# Content changes on these paths are treated as critical drift.
SENSITIVE_CONFIG_PATHS = {
    "/etc/sudoers",
    "/etc/ssh/sshd_config",
    "/etc/passwd",
    "/etc/shadow",
    "/etc/sudoers.d/",
}

# Basenames that are sensitive regardless of absolute path (cross-environment).
SENSITIVE_CONFIG_BASENAMES = {"sshd_config", "sudoers", "passwd", "shadow"}


def _is_sensitive(path: str) -> bool:
    if any(path == p or path.startswith(p) for p in SENSITIVE_CONFIG_PATHS):
        return True
    basename = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return basename in SENSITIVE_CONFIG_BASENAMES

BASELINE_DIR = Path("data") / "config_baseline"


SCHEMA = ToolSchema(
    name="config_drift_check",
    description="Detect critical config file drift by comparing current fingerprints against a stored baseline (read-only)",
    input_schema={
        "type": "object",
        "properties": {
            "baseline_name": {
                "type": "string",
                "description": "Baseline name to compare against (default: default)",
                "maxLength": 64,
            },
            "save_baseline": {
                "type": "integer",
                "description": "Set to 1 to save current fingerprints as a new baseline (writes to data/ only)",
                "minimum": 0,
                "maximum": 1,
            },
        },
        "required": [],
    },
)


def _config_drift_check(baseline_name: str = "default", save_baseline: int = 0) -> ToolResult:
    collected = _collect_fingerprints()
    present_count = sum(1 for item in collected if item.get("status") == "present")

    if save_baseline == 1:
        saved = _save_baseline(baseline_name, collected)
        return ToolResult(
            tool="config_drift_check",
            status="success",
            data={
                "action": "baseline_saved",
                "baseline_name": baseline_name,
                "baseline_path": str(saved),
                "collected_count": len(collected),
                "present_count": present_count,
                "collected": collected,
                "note": "已将当前配置指纹保存为基线，后续 config_drift_check 将以此为对比基准",
            },
            raw_output=f"baseline saved: {saved}, collected {present_count} present files",
        )

    baseline_path = BASELINE_DIR / f"{_safe_name(baseline_name)}.json"
    if not baseline_path.exists():
        return ToolResult(
            tool="config_drift_check",
            status="success",
            data={
                "action": "collect_only",
                "baseline_name": baseline_name,
                "baseline_exists": False,
                "collected_count": len(collected),
                "present_count": present_count,
                "drift_count": 0,
                "drift_items": [],
                "collected": collected,
                "note": "未找到基线，本次仅采集当前配置指纹；建议先以 save_baseline=1 建立基线，再做漂移对比",
            },
            raw_output=f"no baseline, collected {present_count} present files",
        )

    try:
        baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ToolResult(
            tool="config_drift_check",
            status="parse_warning",
            error="baseline file unreadable",
            data={"collected": collected, "drift_items": []},
        )

    drift_items = _compare_baseline(baseline_data, collected)
    critical_count = sum(1 for d in drift_items if d.get("severity") == "critical")

    # Record drift on a timeline so a later failure can be correlated back
    # to the change that likely caused it (change-induced failure analysis).
    recorded_at = time.time()
    if drift_items:
        try:
            from backend.analysis.change_log import get_change_log
            get_change_log().record(drift_items, detected_at=recorded_at)
        except Exception:
            # Timeline persistence is auxiliary; never fail the drift check.
            pass

    return ToolResult(
        tool="config_drift_check",
        status="success",
        data={
            "action": "drift_compare",
            "baseline_name": baseline_name,
            "baseline_exists": True,
            "baseline_created_at": baseline_data.get("created_at"),
            "collected_count": len(collected),
            "present_count": present_count,
            "drift_count": len(drift_items),
            "critical_drift_count": critical_count,
            "drift_items": drift_items,
            "detected_at": recorded_at,
            "collected": collected,
        },
        raw_output=f"drift check: {len(drift_items)} drift items, {critical_count} critical",
    )


def _collect_fingerprints() -> list[dict[str, Any]]:
    """Collect read-only fingerprints for whitelisted critical config files."""
    collected: list[dict[str, Any]] = []
    for path in CRITICAL_CONFIG_PATHS:
        item: dict[str, Any] = {"path": path, "exists": False}
        if not os.path.exists(path):
            item["status"] = "missing"
            collected.append(item)
            continue
        try:
            stat = os.stat(path)
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            item.update({
                "exists": True,
                "status": "present",
                "sha256": digest,
                "mode": oct(stat.st_mode & 0o777),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "uid": stat.st_uid,
                "gid": stat.st_gid,
            })
        except PermissionError:
            item["status"] = "permission_denied"
        except OSError as exc:
            item["status"] = "error"
            item["error"] = str(exc)
        collected.append(item)
    return collected


def _compare_baseline(baseline: dict[str, Any], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare current fingerprints against baseline, return drift items."""
    baseline_map = {item["path"]: item for item in baseline.get("collected", []) if isinstance(item, dict)}
    current_map = {item["path"]: item for item in current}
    drifts: list[dict[str, Any]] = []

    all_paths = set(baseline_map) | set(current_map)
    for path in sorted(all_paths):
        base = baseline_map.get(path)
        curr = current_map.get(path)
        base_exists = bool(base and base.get("exists"))
        curr_exists = bool(curr and curr.get("exists"))

        if not base_exists and not curr_exists:
            continue
        if base_exists and not curr_exists:
            drifts.append({
                "path": path,
                "change": "deleted",
                "severity": "critical",
                "note": "基线中存在但当前缺失，疑似被删除",
            })
            continue
        if curr_exists and not base_exists:
            drifts.append({
                "path": path,
                "change": "added",
                "severity": "warning",
                "note": "当前存在但基线中没有，疑似新增配置",
            })
            continue

        changes: list[str] = []
        if base.get("sha256") != curr.get("sha256"):
            changes.append("content_modified")
        if base.get("mode") != curr.get("mode"):
            changes.append("mode_changed")
        if base.get("uid") != curr.get("uid") or base.get("gid") != curr.get("gid"):
            changes.append("owner_changed")

        if not changes:
            continue

        is_sensitive = _is_sensitive(path)
        severity = "critical" if ("content_modified" in changes and is_sensitive) else "warning"
        drifts.append({
            "path": path,
            "change": changes,
            "severity": severity,
            "baseline_sha256": base.get("sha256"),
            "current_sha256": curr.get("sha256"),
            "baseline_mode": base.get("mode"),
            "current_mode": curr.get("mode"),
            "note": _drift_note(path, changes, is_sensitive),
        })

    return drifts


def _drift_note(path: str, changes: list[str], sensitive: bool) -> str:
    parts = []
    if "content_modified" in changes:
        parts.append("内容已修改")
    if "mode_changed" in changes:
        parts.append("权限已变更")
    if "owner_changed" in changes:
        parts.append("属主/属组已变更")
    suffix = "（敏感配置，建议立即核对是否为授权变更）" if sensitive else ""
    return "、".join(parts) + suffix


def _save_baseline(name: str, collected: list[dict[str, Any]]) -> Path:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(name)
    path = BASELINE_DIR / f"{safe}.json"
    payload = {
        "name": name,
        "created_at": int(time.time()),
        "collected": collected,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _safe_name(name: str) -> str:
    keep = [c for c in name if c.isalnum() or c in ("-", "_")]
    return "".join(keep) or "default"


def register() -> None:
    get_registry().register(
        SCHEMA,
        lambda baseline_name="default", save_baseline=0: _config_drift_check(baseline_name, save_baseline),
    )
