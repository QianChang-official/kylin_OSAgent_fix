"""Tests for blast-radius impact analysis.

Covers the innovation claim: before touching a file the system can predict
*what breaks*, including the handle-leak trap that makes naive `rm` on an
open log file fail to reclaim any disk space.
"""
import pytest

from backend.analysis import build_diagnosis
from backend.tools.impact_tool import _human_size, _impact_analysis, register
from backend.tools.registry import get_registry


class _FakeResult:
    def __init__(self, stdout="", success=True, error="", stderr="", command=None):
        self.stdout = stdout
        self.success = success
        self.error = error
        self.stderr = stderr
        self.command = command or []
        self.executor_user = "test"
        self.duration_ms = 0
        self.returncode = 0 if success else 1


LSOF_NGINX_LOG = """COMMAND  PID  USER   FD   TYPE DEVICE SIZE/OFF     NODE NAME
nginx   1234  root    5w   REG   8,1  5368709120  1441801 /var/log/nginx/access.log
nginx   1235 nginx    5w   REG   8,1  5368709120  1441801 /var/log/nginx/access.log
"""

LSOF_TWO_SERVICES = """COMMAND  PID  USER   FD   TYPE DEVICE SIZE/OFF     NODE NAME
nginx   1234  root    5w   REG   8,1  1024  1441801 /var/data/shared.db
mysqld  2345 mysql    7u   REG   8,1  1024  1441801 /var/data/shared.db
"""

SS_OUTPUT = """Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*    users:(("nginx",pid=1234,fd=6))
"""


@pytest.fixture()
def patched(monkeypatch):
    """Route the tool's executor and cgroup lookup through fakes."""
    def _apply(lsof_output="", lsof_success=True, lsof_error="", ss_output="", unit=""):
        def fake_run(cmd, *args, **kwargs):
            if cmd and cmd[0] == "lsof":
                return _FakeResult(stdout=lsof_output, success=lsof_success,
                                   error=lsof_error, command=cmd)
            if cmd and cmd[0] == "ss":
                return _FakeResult(stdout=ss_output, success=bool(ss_output), command=cmd)
            return _FakeResult(success=False, error="unexpected command", command=cmd)

        monkeypatch.setattr("backend.tools.impact_tool._executor.run", fake_run)
        monkeypatch.setattr("backend.tools.impact_tool._systemd_unit_for", lambda pid: unit)
    return _apply


# ---------- core behaviour ----------

def test_missing_path_returns_no_impact(patched, tmp_path):
    patched()
    result = _impact_analysis(str(tmp_path / "does-not-exist.log"))
    assert result.data["exists"] is False
    assert result.data["blast_radius"] == "none"
    assert result.data["safe_action"] == "no_action"


def test_empty_path_rejected():
    result = _impact_analysis("")
    assert result.status == "command_failed"


def test_file_without_holders_is_safe_to_remove(patched, tmp_path):
    target = tmp_path / "orphan.log"
    target.write_text("x" * 100, encoding="utf-8")
    patched(lsof_output="", lsof_success=False)

    result = _impact_analysis(str(target))
    assert result.data["holder_count"] == 0
    assert result.data["handle_leak_risk"] is False
    assert result.data["blast_radius"] == "isolated"
    assert result.data["safe_action"] == "safe_to_remove"
    assert "safe_cleanup_plan" in result.data["recommendation"]


def test_open_log_file_warns_about_handle_leak(patched, tmp_path):
    """The core insight: rm on an open log does not free the space."""
    target = tmp_path / "access.log"
    target.write_text("x" * 1000, encoding="utf-8")
    patched(lsof_output=LSOF_NGINX_LOG, ss_output=SS_OUTPUT, unit="nginx.service")

    result = _impact_analysis(str(target))
    assert result.data["holder_count"] == 2
    assert result.data["handle_leak_risk"] is True
    assert result.data["safe_action"] == "truncate_or_logrotate"
    joined = " ".join(result.data["warnings"])
    assert "句柄" in joined
    assert "truncate" in result.data["recommendation"]
    # An operator must be told explicitly not to rm it.
    assert "不要直接 rm" in result.data["recommendation"]


def test_open_non_log_file_requires_manual_review(patched, tmp_path):
    target = tmp_path / "shared.dat"
    target.write_text("x", encoding="utf-8")
    patched(lsof_output=LSOF_NGINX_LOG.replace("access.log", "shared.dat"), unit="nginx.service")

    result = _impact_analysis(str(target))
    assert result.data["safe_action"] == "manual_review"
    assert result.data["severity"] == "critical"


def test_multiple_services_escalate_blast_radius(patched, tmp_path):
    target = tmp_path / "shared.db"
    target.write_text("x", encoding="utf-8")

    units = {"1234": "nginx.service", "2345": "mysqld.service"}
    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "lsof":
            return _FakeResult(stdout=LSOF_TWO_SERVICES, command=cmd)
        return _FakeResult(success=False, command=cmd)

    import backend.tools.impact_tool as module
    module._executor.run = fake_run  # type: ignore[assignment]
    original = module._systemd_unit_for
    module._systemd_unit_for = lambda pid: units.get(pid, "")  # type: ignore[assignment]
    try:
        result = _impact_analysis(str(target))
    finally:
        module._systemd_unit_for = original  # type: ignore[assignment]

    assert result.data["blast_radius"] == "multi_service"
    assert result.data["severity"] == "critical"
    assert len(result.data["affected_services"]) == 2


def test_listening_ports_are_reported(patched, tmp_path):
    target = tmp_path / "access.log"
    target.write_text("x", encoding="utf-8")
    patched(lsof_output=LSOF_NGINX_LOG, ss_output=SS_OUTPUT, unit="nginx.service")

    result = _impact_analysis(str(target))
    ports = {item["port"] for item in result.data["affected_ports"]}
    assert "80" in ports
    assert any("端口" in warning for warning in result.data["warnings"])


def test_lsof_missing_reports_capability_missing(patched, tmp_path):
    target = tmp_path / "a.log"
    target.write_text("x", encoding="utf-8")
    patched(lsof_success=False, lsof_error="lsof: not found")

    result = _impact_analysis(str(target))
    assert result.status == "capability_missing"


def test_systemd_units_are_surfaced(patched, tmp_path):
    target = tmp_path / "access.log"
    target.write_text("x", encoding="utf-8")
    patched(lsof_output=LSOF_NGINX_LOG, unit="nginx.service")

    result = _impact_analysis(str(target))
    service = result.data["affected_services"][0]
    assert service["systemd_unit"] == "nginx.service"
    assert service["managed_by_systemd"] is True


# ---------- helpers ----------

@pytest.mark.parametrize("size,expected", [
    (None, "未知"),
    (512, "512B"),
    (2048, "2.0KB"),
    (5 * 1024 * 1024, "5.0MB"),
])
def test_human_size(size, expected):
    assert _human_size(size) == expected


def test_register_adds_tool_to_registry():
    register()
    schema = get_registry().get_schema("impact_analysis")
    assert schema is not None
    assert "path" in schema.input_schema["required"]


# ---------- diagnosis integration ----------

def test_build_diagnosis_parses_handle_leak():
    diagnosis = build_diagnosis([
        {
            "tool": "impact_analysis",
            "status": "success",
            "data": {
                "path": "/var/log/nginx/access.log",
                "exists": True,
                "holder_count": 2,
                "handle_leak_risk": True,
                "severity": "warning",
                "safe_action": "truncate_or_logrotate",
                "affected_services": [{"name": "nginx.service"}],
                "warnings": ["该文件正被 2 个进程持有句柄"],
                "recommendation": "不要直接 rm，应使用 truncate。",
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "warning"
    assert any("句柄" in item for item in diagnosis["findings"])
    assert any("truncate" in item for item in diagnosis["next_actions"])
    evidence = {item["metric"]: item["value"] for item in diagnosis["evidence"]}
    assert evidence["impact_holder_count"] == 2.0


def test_build_diagnosis_parses_isolated_file():
    diagnosis = build_diagnosis([
        {
            "tool": "impact_analysis",
            "status": "success",
            "data": {
                "path": "/tmp/orphan.log",
                "exists": True,
                "holder_count": 0,
                "handle_leak_risk": False,
                "severity": "info",
                "safe_action": "safe_to_remove",
                "affected_services": [],
                "warnings": [],
                "recommendation": "可纳入 safe_cleanup_plan。",
            },
        }
    ], execution_status="success", security_decision="allow")

    assert any("影响面隔离" in item for item in diagnosis["findings"])
    assert any("safe_cleanup_plan" in item for item in diagnosis["next_actions"])
