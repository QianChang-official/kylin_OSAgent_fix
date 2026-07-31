"""Tests for the config_drift_check tool.

Covers competition scenario "configuration file drift": fingerprint
collection, baseline save, drift detection (content / mode / deleted /
added), and sensitive config critical severity.
"""
import json
import os
import sys

import pytest

from backend.tools.config_drift_tool import (
    CRITICAL_CONFIG_PATHS,
    _collect_fingerprints,
    _config_drift_check,
    register,
)
from backend.tools.registry import get_registry


def test_collect_fingerprints_returns_whitelist_count():
    result = _collect_fingerprints()
    assert len(result) == len(CRITICAL_CONFIG_PATHS)
    assert all("path" in item for item in result)


def test_config_drift_check_collect_only_when_no_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "sshd_config"), str(tmp_path / "hosts")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    (tmp_path / "sshd_config").write_text("Port 22")
    (tmp_path / "hosts").write_text("127.0.0.1 localhost")

    result = _config_drift_check()
    assert result.status == "success"
    assert result.data["action"] == "collect_only"
    assert result.data["present_count"] == 2
    assert result.data["drift_count"] == 0
    assert result.data["baseline_exists"] is False


def test_config_drift_check_save_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "sshd_config")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    (tmp_path / "sshd_config").write_text("Port 22")

    result = _config_drift_check(save_baseline=1)
    assert result.status == "success"
    assert result.data["action"] == "baseline_saved"
    assert (tmp_path / "default.json").exists()
    baseline = json.loads((tmp_path / "default.json").read_text(encoding="utf-8"))
    assert baseline["collected"][0]["sha256"]


def test_config_drift_check_detects_content_modification_critical(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "sshd_config")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    (tmp_path / "sshd_config").write_text("Port 22")
    _config_drift_check(save_baseline=1)
    (tmp_path / "sshd_config").write_text("Port 2222 PermitRootLogin yes")

    result = _config_drift_check()
    assert result.status == "success"
    assert result.data["action"] == "drift_compare"
    assert result.data["drift_count"] == 1
    assert result.data["critical_drift_count"] == 1
    drift = result.data["drift_items"][0]
    assert drift["change"] == ["content_modified"]
    assert drift["severity"] == "critical"
    assert "敏感配置" in drift["note"]


@pytest.mark.skipif(sys.platform == "win32", reason="Unix permission bits not fully honored on Windows; verified on Kylin Linux")
def test_config_drift_check_detects_mode_change(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "hosts")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    f = tmp_path / "hosts"
    f.write_text("127.0.0.1 localhost")
    os.chmod(f, 0o644)
    _config_drift_check(save_baseline=1)
    os.chmod(f, 0o777)

    result = _config_drift_check()
    assert result.data["drift_count"] == 1
    assert "mode_changed" in result.data["drift_items"][0]["change"]


def test_config_drift_check_detects_deleted_file(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "crontab")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    f = tmp_path / "crontab"
    f.write_text("cron content")
    _config_drift_check(save_baseline=1)
    f.unlink()

    result = _config_drift_check()
    assert result.data["drift_count"] == 1
    assert result.data["drift_items"][0]["change"] == "deleted"
    assert result.data["drift_items"][0]["severity"] == "critical"


def test_config_drift_check_detects_added_file(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "fstab")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    _config_drift_check(save_baseline=1)
    (tmp_path / "fstab").write_text("fstab content")

    result = _config_drift_check()
    assert result.data["drift_count"] == 1
    assert result.data["drift_items"][0]["change"] == "added"


def test_config_drift_check_no_drift_after_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "hosts")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    (tmp_path / "hosts").write_text("127.0.0.1 localhost")
    _config_drift_check(save_baseline=1)

    result = _config_drift_check()
    assert result.data["drift_count"] == 0
    assert result.data["action"] == "drift_compare"


def test_config_drift_check_uses_named_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.tools.config_drift_tool.BASELINE_DIR", tmp_path)
    fake_paths = [str(tmp_path / "hosts")]
    monkeypatch.setattr("backend.tools.config_drift_tool.CRITICAL_CONFIG_PATHS", fake_paths)
    (tmp_path / "hosts").write_text("127.0.0.1 localhost")
    _config_drift_check(baseline_name="production", save_baseline=1)

    assert (tmp_path / "production.json").exists()
    result = _config_drift_check(baseline_name="production")
    assert result.data["baseline_name"] == "production"
    assert result.data["drift_count"] == 0


def test_register_adds_config_drift_check_to_registry():
    register()
    schema = get_registry().get_schema("config_drift_check")
    assert schema is not None
    assert schema.name == "config_drift_check"
    assert "baseline_name" in schema.input_schema.get("properties", {})


def test_build_diagnosis_parses_config_drift_critical():
    from backend.analysis import build_diagnosis

    diagnosis = build_diagnosis([
        {
            "tool": "config_drift_check",
            "status": "success",
            "data": {
                "action": "drift_compare",
                "present_count": 10,
                "drift_count": 2,
                "critical_drift_count": 1,
                "drift_items": [
                    {"path": "/etc/sudoers", "change": ["content_modified"], "severity": "critical", "note": "内容已修改（敏感配置，建议立即核对是否为授权变更）"},
                    {"path": "/etc/hosts", "change": ["content_modified"], "severity": "warning", "note": "内容已修改"},
                ],
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "critical"
    assert any("sudoers" in item for item in diagnosis["findings"])
    assert any("敏感配置" in item for item in diagnosis["recommendations"])
    assert any("回滚" in item for item in diagnosis["next_actions"])
    evidence = {item["metric"]: item["value"] for item in diagnosis["evidence"]}
    assert evidence["config_drift_count"] == 2.0
    assert evidence["config_critical_drift_count"] == 1.0


def test_build_diagnosis_parses_config_drift_no_drift():
    from backend.analysis import build_diagnosis

    diagnosis = build_diagnosis([
        {
            "tool": "config_drift_check",
            "status": "success",
            "data": {
                "action": "drift_compare",
                "present_count": 10,
                "drift_count": 0,
                "critical_drift_count": 0,
                "drift_items": [],
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "normal"
    assert any("未发现漂移" in item for item in diagnosis["findings"])
