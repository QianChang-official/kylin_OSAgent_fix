"""Tests for change-induced failure correlation.

Covers the innovation claim: the engine can answer "which change caused
this failure?", not just "what is broken right now?".
"""
import time

import pytest

from backend.analysis.change_log import ChangeLog, infer_service
from backend.analysis.root_cause_engine import build_root_cause_chains


def _drift_result(drift_items, detected_at=None):
    return {
        "tool": "config_drift_check",
        "status": "success",
        "data": {
            "action": "drift_compare",
            "drift_count": len(drift_items),
            "drift_items": drift_items,
            "detected_at": detected_at if detected_at is not None else time.time(),
        },
    }


def _service_result(name, state):
    return {
        "tool": "get_service_status",
        "status": "success",
        "data": {"service_name": name, "active_state": state},
    }


def _journal_result(rows):
    return {"tool": "journal_query", "status": "success", "data": rows}


SSHD_DRIFT = {
    "path": "/etc/ssh/sshd_config",
    "change": ["content_modified"],
    "severity": "critical",
    "note": "内容已修改（敏感配置）",
}


# ---------- service inference ----------

def test_infer_service_from_config_path():
    assert infer_service("/etc/ssh/sshd_config") == "sshd"
    assert infer_service("/etc/my.cnf") == "mysqld"
    assert infer_service("/etc/fstab") == "mount"


def test_infer_service_unknown_path_returns_empty():
    assert infer_service("/opt/custom/whatever.conf") == ""


# ---------- change log ----------

def test_change_log_records_and_reads(tmp_path):
    log = ChangeLog(path=tmp_path / "changes.jsonl")
    assert log.record([SSHD_DRIFT]) == 1
    events = log.recent()
    assert len(events) == 1
    assert events[0]["path"] == "/etc/ssh/sshd_config"
    assert events[0]["affected_service"] == "sshd"
    assert events[0]["detected_at"] > 0


def test_change_log_empty_when_no_file(tmp_path):
    assert ChangeLog(path=tmp_path / "missing.jsonl").recent() == []


def test_change_log_time_window_filter(tmp_path):
    log = ChangeLog(path=tmp_path / "changes.jsonl")
    now = time.time()
    log.record([SSHD_DRIFT], detected_at=now - 10_000)
    log.record([{"path": "/etc/hosts", "change": ["content_modified"], "severity": "warning"}],
               detected_at=now - 60)

    recent = log.recent(within_seconds=600, now=now)
    assert len(recent) == 1
    assert recent[0]["path"] == "/etc/hosts"


def test_change_log_newest_first(tmp_path):
    log = ChangeLog(path=tmp_path / "changes.jsonl")
    now = time.time()
    log.record([{"path": "/etc/hosts", "change": ["x"], "severity": "warning"}], detected_at=now - 500)
    log.record([SSHD_DRIFT], detected_at=now - 10)
    events = log.recent()
    assert events[0]["path"] == "/etc/ssh/sshd_config"


def test_change_log_trims_to_max(tmp_path):
    log = ChangeLog(path=tmp_path / "changes.jsonl", max_events=5)
    for index in range(12):
        log.record([{"path": f"/etc/f{index}", "change": ["x"], "severity": "warning"}])
    assert len(log.recent()) == 5


def test_change_log_ignores_corrupt_lines(tmp_path):
    path = tmp_path / "changes.jsonl"
    path.write_text('{"path": "/etc/hosts", "detected_at": 1}\nNOT JSON\n', encoding="utf-8")
    assert len(ChangeLog(path=path).recent()) == 1


def test_change_log_record_empty_returns_zero(tmp_path):
    assert ChangeLog(path=tmp_path / "changes.jsonl").record([]) == 0


# ---------- correlation detector ----------

def test_change_induced_failure_detected():
    chains = build_root_cause_chains([
        _drift_result([SSHD_DRIFT]),
        _service_result("sshd", "failed"),
    ])
    chain = next(c for c in chains if c["chain_id"] == "change_induced_failure")
    assert "sshd" in chain["root_cause"]
    assert "/etc/ssh/sshd_config" in chain["root_cause"]
    assert chain["severity"] == "critical"
    assert chain["safety_assessment"]["change_correlated"] is True


def test_change_induced_failure_reports_lead_time():
    """The operator needs to know how long before the failure it changed."""
    chains = build_root_cause_chains([
        _drift_result([SSHD_DRIFT], detected_at=time.time() - 720),  # 12 minutes ago
        _service_result("sshd", "failed"),
    ])
    chain = next(c for c in chains if c["chain_id"] == "change_induced_failure")
    assert "分钟前" in chain["root_cause"]
    lead = {item["metric"]: item["value"] for item in chain["evidence"]}["change_lead_minutes"]
    assert 11.5 <= lead <= 12.5


def test_change_outside_window_has_no_lead_time():
    chains = build_root_cause_chains([
        _drift_result([SSHD_DRIFT], detected_at=time.time() - 100_000),
        _service_result("sshd", "failed"),
    ])
    chain = next(c for c in chains if c["chain_id"] == "change_induced_failure")
    assert "分钟前" not in chain["root_cause"]


def test_drift_without_failure_produces_no_chain():
    """A change on a healthy system is not a root cause."""
    chains = build_root_cause_chains([
        _drift_result([SSHD_DRIFT]),
        _service_result("sshd", "active"),
    ])
    assert not [c for c in chains if c["chain_id"] == "change_induced_failure"]


def test_failure_without_related_change_produces_no_chain():
    """An unrelated file changing must not be blamed for the failure."""
    chains = build_root_cause_chains([
        _drift_result([{"path": "/etc/hosts", "change": ["content_modified"], "severity": "warning"}]),
        _service_result("sshd", "failed"),
    ])
    assert not [c for c in chains if c["chain_id"] == "change_induced_failure"]


def test_journal_evidence_alone_yields_lower_confidence():
    with_service = build_root_cause_chains([
        _drift_result([SSHD_DRIFT]),
        _service_result("sshd", "failed"),
    ])
    with_journal = build_root_cause_chains([
        _drift_result([SSHD_DRIFT]),
        _journal_result([{"content": "sshd: error while loading configuration"}]),
    ])
    service_chain = next(c for c in with_service if c["chain_id"] == "change_induced_failure")
    journal_chain = next(c for c in with_journal if c["chain_id"] == "change_induced_failure")
    assert journal_chain["confidence"] < service_chain["confidence"]


def test_no_drift_data_produces_no_chain():
    chains = build_root_cause_chains([_service_result("sshd", "failed")])
    assert not [c for c in chains if c["chain_id"] == "change_induced_failure"]


def test_empty_drift_items_produces_no_chain():
    chains = build_root_cause_chains([
        _drift_result([]),
        _service_result("sshd", "failed"),
    ])
    assert not [c for c in chains if c["chain_id"] == "change_induced_failure"]


def test_change_chain_recommends_rollback_verification():
    chains = build_root_cause_chains([
        _drift_result([SSHD_DRIFT]),
        _service_result("sshd", "failed"),
    ])
    chain = next(c for c in chains if c["chain_id"] == "change_induced_failure")
    joined = " ".join(chain["recommendations"])
    assert "回滚" in joined
    assert "基线" in joined
    # Rollback is a write operation and must stay behind human confirmation.
    assert "人工确认" in chain["safety_assessment"]["notes"]


def test_change_chain_ranks_above_generic_chains():
    """Change correlation is the more actionable conclusion, so it should
    not be buried below a generic disk-pressure chain."""
    chains = build_root_cause_chains([
        _drift_result([SSHD_DRIFT]),
        _service_result("sshd", "failed"),
        {
            "tool": "disk_usage",
            "status": "success",
            "data": [{"filesystem": "/dev/sda1", "mounted_on": "/", "use_percent": "96%"}],
        },
        {
            "tool": "large_file_scan",
            "status": "success",
            "data": {"files": [{"path": "/var/log/app.log", "size": "5GB"}]},
        },
    ])
    assert chains[0]["chain_id"] == "change_induced_failure"


def test_config_drift_tool_writes_change_timeline(tmp_path, monkeypatch):
    """Running the real tool must append to the timeline."""
    import backend.analysis.change_log as change_log_module
    from backend.tools import config_drift_tool

    log = ChangeLog(path=tmp_path / "changes.jsonl")
    monkeypatch.setattr(change_log_module, "get_change_log", lambda: log)

    target = tmp_path / "sshd_config"
    target.write_text("PermitRootLogin no\n", encoding="utf-8")
    monkeypatch.setattr(config_drift_tool, "CRITICAL_CONFIG_PATHS", [str(target)])
    monkeypatch.setattr(config_drift_tool, "BASELINE_DIR", tmp_path / "baseline")

    config_drift_tool._config_drift_check(save_baseline=1)
    target.write_text("PermitRootLogin yes\n", encoding="utf-8")
    result = config_drift_tool._config_drift_check()

    assert result.data["drift_count"] == 1
    events = log.recent()
    assert len(events) == 1
    assert events[0]["affected_service"] == "sshd"
