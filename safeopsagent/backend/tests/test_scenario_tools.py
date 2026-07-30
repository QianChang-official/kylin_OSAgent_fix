"""Tests for scenario-driven tools: zombie process check and disk I/O analysis.

Covers competition scenario pain points "zombie process accumulation"
and "disk I/O anomaly".
"""
import pytest

from backend.tools.zombie_process_tool import _zombie_process_check, register as register_zombie
from backend.tools.disk_io_tool import _disk_io_analysis, _parse_iostat, register as register_disk_io
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


# ---------- zombie_process_check ----------

PS_NO_ZOMBIES = """  PID  PPID USER     STAT COMM            ARGS
    1     0 root     Ss   systemd          /sbin/init
 1234     1 root     S    nginx            nginx: worker process
"""

PS_WITH_ZOMBIES = """  PID  PPID USER     STAT COMM            ARGS
    1     0 root     Ss   systemd          /sbin/init
 1234     1 root     S    nginx            nginx: master process
 2000  1234 root     Z    nginx            [nginx] <defunct>
 2001  1234 root     Z    nginx            [nginx] <defunct>
"""

PS_PARENT_INFO = """  PID USER     STAT COMM            ARGS
 1234 root     S    nginx            nginx: master process
"""


def test_zombie_process_check_no_zombies(monkeypatch):
    def fake_run(cmd):
        if "-p" in cmd:
            return _FakeResult(stdout=PS_PARENT_INFO, command=cmd)
        return _FakeResult(stdout=PS_NO_ZOMBIES, command=cmd)
    monkeypatch.setattr("backend.tools.zombie_process_tool._executor.run", fake_run)

    result = _zombie_process_check()
    assert result.status == "success"
    assert result.data["zombie_count"] == 0
    assert "正常" in result.data["recommendation"]


def test_zombie_process_check_detects_zombies(monkeypatch):
    def fake_run(cmd):
        if "-p" in cmd:
            return _FakeResult(stdout=PS_PARENT_INFO, command=cmd)
        return _FakeResult(stdout=PS_WITH_ZOMBIES, command=cmd)
    monkeypatch.setattr("backend.tools.zombie_process_tool._executor.run", fake_run)

    result = _zombie_process_check()
    assert result.status == "success"
    assert result.data["zombie_count"] == 2
    assert len(result.data["zombies"]) == 2
    assert result.data["parents"]
    assert "nginx" in result.data["recommendation"]
    assert "重启" in result.data["recommendation"] or "reap" in result.data["recommendation"]


PS_ZOMBIE_INIT_PARENT = """  PID  PPID USER     STAT COMM            ARGS
    1     0 root     Ss   systemd          /sbin/init
 3000     1 root     Z    orphan           [orphan] <defunct>
"""

PS_INIT_PARENT_INFO = """  PID USER     STAT COMM            ARGS
    1 root     Ss   systemd          /sbin/init
"""


def test_zombie_process_check_init_parent_advises_recheck(monkeypatch):
    """Zombies reaped by init(PID 1) must not trigger a service-restart advice."""
    def fake_run(cmd):
        if "-p" in cmd:
            return _FakeResult(stdout=PS_INIT_PARENT_INFO, command=cmd)
        return _FakeResult(stdout=PS_ZOMBIE_INIT_PARENT, command=cmd)
    monkeypatch.setattr("backend.tools.zombie_process_tool._executor.run", fake_run)

    result = _zombie_process_check()
    assert result.status == "success"
    assert result.data["zombie_count"] == 1
    assert result.data["parents"][0]["is_init"] is True
    recommendation = result.data["recommendation"]
    assert "init" in recommendation
    assert "复测" in recommendation
    assert "重启" not in recommendation


def test_zombie_process_check_capability_missing(monkeypatch):
    monkeypatch.setattr(
        "backend.tools.zombie_process_tool._executor.run",
        lambda cmd: _FakeResult(success=False, error="ps: not found", command=cmd),
    )
    result = _zombie_process_check()
    assert result.status == "capability_missing"


def test_zombie_process_check_register():
    register_zombie()
    schema = get_registry().get_schema("zombie_process_check")
    assert schema is not None
    assert schema.name == "zombie_process_check"


# ---------- disk_io_analysis ----------

IOSTAT_NORMAL = """Linux 5.15.0 (host) \t07/29/2026 \t_x86_64_\t(2 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           1.00    0.00    0.50    0.00    0.00   98.50

Device         r/s     w/s   r_await w_await  svctm  %util
sda           10.00    5.00    1.00    2.00   0.50   0.30
"""

IOSTAT_WITH_BOTTLENECK = """Linux 5.15.0 (host) \t07/29/2026 \t_x86_64_\t(2 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           1.00    0.00    0.50    0.00    0.00   98.50

Device         r/s     w/s   r_await w_await  svctm  %util
sda           10.00    5.00    1.00    2.00   0.50   0.30

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           2.00    0.00    1.00    5.00    0.00   92.00

Device         r/s     w/s   r_await w_await  svctm  %util
sda          100.00   50.00   55.00   60.00   5.00   95.00
sdb            5.00    2.00    1.00    1.00   0.20   0.10
"""


def test_disk_io_analysis_no_bottleneck(monkeypatch):
    monkeypatch.setattr(
        "backend.tools.disk_io_tool._executor.run",
        lambda cmd: _FakeResult(stdout=IOSTAT_NORMAL, command=cmd),
    )
    result = _disk_io_analysis()
    assert result.status == "success"
    assert result.data["bottleneck_count"] == 0
    assert "未发现" in result.data["recommendation"]


def test_disk_io_analysis_detects_bottleneck(monkeypatch):
    monkeypatch.setattr(
        "backend.tools.disk_io_tool._executor.run",
        lambda cmd: _FakeResult(stdout=IOSTAT_WITH_BOTTLENECK, command=cmd),
    )
    result = _disk_io_analysis()
    assert result.status == "success"
    assert result.data["bottleneck_count"] == 1
    bottleneck = result.data["bottlenecks"][0]
    assert bottleneck["device"] == "sda"
    assert bottleneck["util_percent"] == 95.0
    assert "sda" in result.data["recommendation"]


IOSTAT_HIGH_AWAIT_ONLY = """Linux 5.15.0 (host) \t07/29/2026 \t_x86_64_\t(2 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           1.00    0.00    0.50    0.00    0.00   98.50

Device         r/s     w/s   r_await w_await  svctm  %util
sdc            8.00    4.00    1.00    1.00   0.20   0.20

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           2.00    0.00    1.00    8.00    0.00   89.00

Device         r/s     w/s   r_await w_await  svctm  %util
sdc            8.00    4.00   70.00   90.00   1.00  12.00
"""


def test_disk_io_analysis_detects_await_only_bottleneck(monkeypatch):
    """A device can be a bottleneck on latency alone, even with low %util."""
    monkeypatch.setattr(
        "backend.tools.disk_io_tool._executor.run",
        lambda cmd: _FakeResult(stdout=IOSTAT_HIGH_AWAIT_ONLY, command=cmd),
    )
    result = _disk_io_analysis()
    assert result.status == "success"
    assert result.data["bottleneck_count"] == 1
    bottleneck = result.data["bottlenecks"][0]
    assert bottleneck["device"] == "sdc"
    assert bottleneck["util_percent"] == 12.0      # below the 80% util threshold
    assert bottleneck["await_ms"] == 80.0          # (70 + 90) / 2, above the 50ms threshold


def test_disk_io_analysis_capability_missing(monkeypatch):
    monkeypatch.setattr(
        "backend.tools.disk_io_tool._executor.run",
        lambda cmd: _FakeResult(success=False, error="iostat: not found", command=cmd),
    )
    result = _disk_io_analysis()
    assert result.status == "capability_missing"


def test_parse_iostat_takes_second_sample():
    devices = _parse_iostat(IOSTAT_WITH_BOTTLENECK)
    # Should parse the second sample block (sda high util + sdb normal)
    names = [d["device"] for d in devices]
    assert "sda" in names
    assert "sdb" in names
    sda = next(d for d in devices if d["device"] == "sda")
    assert sda["util_percent"] == 95.0


def test_disk_io_register():
    register_disk_io()
    schema = get_registry().get_schema("disk_io_analysis")
    assert schema is not None
    assert schema.name == "disk_io_analysis"


# ---------- build_diagnosis integration ----------

def test_build_diagnosis_parses_zombie_process():
    from backend.analysis import build_diagnosis

    diagnosis = build_diagnosis([
        {
            "tool": "zombie_process_check",
            "status": "success",
            "data": {
                "zombie_count": 3,
                "zombies": [{"pid": "2000", "ppid": "1234", "comm": "nginx"}],
                "parents": [{"ppid": "1234", "comm": "nginx", "is_init": False}],
                "recommendation": "检测到 3 个僵尸进程。建议重启 nginx 服务 reap 子进程。",
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "warning"
    assert any("僵尸" in item for item in diagnosis["findings"])
    assert any("nginx" in item for item in diagnosis["recommendations"])
    evidence = {item["metric"]: item["value"] for item in diagnosis["evidence"]}
    assert evidence["zombie_process_count"] == 3.0


def test_build_diagnosis_parses_disk_io_bottleneck():
    from backend.analysis import build_diagnosis

    diagnosis = build_diagnosis([
        {
            "tool": "disk_io_analysis",
            "status": "success",
            "data": {
                "device_count": 2,
                "bottleneck_count": 1,
                "bottlenecks": [{"device": "sda", "util_percent": 95.0, "await_ms": 57.5}],
                "recommendation": "检测到 1 个 I/O 瓶颈设备。sda: util=95.0%, await=57.5ms。建议结合 process_list 定位。",
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "warning"
    assert any("sda" in item for item in diagnosis["findings"])
    evidence = {item["metric"]: item["value"] for item in diagnosis["evidence"]}
    assert evidence["disk_io_bottleneck_count"] == 1.0
