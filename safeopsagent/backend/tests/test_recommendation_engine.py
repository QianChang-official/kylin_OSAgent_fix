from backend.analysis.recommendation_engine import build_diagnosis


def test_memory_diagnosis_uses_real_tool_metrics():
    diagnosis = build_diagnosis([
        {
            "tool": "get_memory_status",
            "status": "success",
            "data": {
                "total_mb": 1000,
                "used_mb": 410,
                "free_mb": 100,
                "available_mb": 590,
                "swap_total_mb": 500,
                "swap_used_mb": 2,
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "normal"
    assert "41.0%" in diagnosis["summary"]
    evidence = {item["metric"]: item["value"] for item in diagnosis["evidence"]}
    assert evidence["memory_usage_percent"] == 41.0
    assert evidence["memory_available"] == 590.0
    assert evidence["swap_usage_percent"] == 0.4


def test_multi_tool_diagnosis_uses_highest_real_severity():
    diagnosis = build_diagnosis([
        {
            "tool": "get_cpu_status",
            "status": "success",
            "data": {
                "usage_percent": 91.0,
                "logical_cores": 4,
                "physical_cores": 2,
                "load_1m": 7.2,
                "load_5m": 5.0,
                "load_15m": 3.0,
                "load_per_core": 1.8,
                "top_processes": [],
            },
        },
        {
            "tool": "disk_usage",
            "status": "success",
            "data": [
                {
                    "mounted_on": "/",
                    "available": "1G",
                    "use_percent": "96%",
                }
            ],
        },
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "critical"
    assert any(item["metric"] == "cpu_usage_percent" for item in diagnosis["evidence"])
    assert any(
        item["metric"] == "disk_usage_percent" and item["context"] == "/"
        for item in diagnosis["evidence"]
    )
    assert any("磁盘" in item or "挂载点" in item for item in diagnosis["recommendations"])


def test_cpu_instantaneous_spike_without_load_is_notice_not_warning():
    diagnosis = build_diagnosis([
        {
            "tool": "get_cpu_status",
            "status": "success",
            "data": {
                "usage_percent": 85.0,
                "logical_cores": 4,
                "load_1m": 0.2,
                "load_5m": 0.1,
                "load_15m": 0.1,
                "load_per_core": 0.05,
                "top_processes": [{"name": "worker", "cpu": 4.0}],
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "notice"
    assert "CPU 瞬时采样 85.0%" in diagnosis["summary"]
    assert "需要尽快处理" not in diagnosis["summary"]
    assert any("间隔复测" in item for item in diagnosis["recommendations"])


def test_normal_memory_and_disk_do_not_turn_cpu_spike_into_urgent_anomaly():
    diagnosis = build_diagnosis([
        {
            "tool": "get_memory_status",
            "status": "success",
            "data": {
                "total_mb": 8000,
                "used_mb": 3200,
                "free_mb": 1800,
                "available_mb": 4800,
                "swap_total_mb": 2000,
                "swap_used_mb": 0,
            },
        },
        {
            "tool": "get_cpu_status",
            "status": "success",
            "data": {
                "usage_percent": 85.0,
                "logical_cores": 4,
                "load_1m": 0.2,
                "load_5m": 0.2,
                "load_15m": 0.1,
                "load_per_core": 0.05,
                "top_processes": [{"name": "worker", "cpu": 4.0}],
            },
        },
        {
            "tool": "disk_usage",
            "status": "success",
            "data": [{"mounted_on": "/", "available": "40G", "use_percent": "35%"}],
        },
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "notice"
    assert diagnosis["summary"].startswith("系统检查发现需要关注的信息。")
    assert "需要尽快处理" not in diagnosis["summary"]


def test_cpu_sustained_pressure_uses_load_and_top_process_evidence():
    diagnosis = build_diagnosis([
        {
            "tool": "get_cpu_status",
            "status": "success",
            "data": {
                "usage_percent": 91.0,
                "logical_cores": 4,
                "load_1m": 5.2,
                "load_5m": 4.8,
                "load_15m": 4.0,
                "load_per_core": 1.3,
                "top_processes": [{"name": "worker", "cpu": 82.0}],
            },
        }
    ], execution_status="success", security_decision="allow")

    assert diagnosis["severity"] == "warning"
    evidence = {item["metric"]: item for item in diagnosis["evidence"]}
    assert evidence["top_cpu_process_percent"]["value"] == 82.0
    assert evidence["top_cpu_process_percent"]["context"] == "worker"


def test_disk_diagnosis_excludes_virtual_filesystems_but_keeps_key_mounts():
    diagnosis = build_diagnosis([
        {
            "tool": "disk_usage",
            "status": "success",
            "data": [
                {
                    "filesystem": "/dev/vda2",
                    "mounted_on": "/",
                    "available": "40G",
                    "use_percent": "35%",
                },
                {
                    "filesystem": "tmpfs",
                    "mounted_on": "/tmp",
                    "available": "2G",
                    "use_percent": "2%",
                },
                {
                    "filesystem": "devtmpfs",
                    "mounted_on": "/dev",
                    "available": "4M",
                    "use_percent": "0%",
                },
                {
                    "filesystem": "cgroup2",
                    "mounted_on": "/sys/fs/cgroup",
                    "available": "0",
                    "use_percent": "0%",
                },
            ],
        }
    ], execution_status="success", security_decision="allow")

    contexts = {item.get("context") for item in diagnosis["evidence"]}
    assert contexts == {"/", "/tmp"}
    assert all("/dev" not in item for item in diagnosis["findings"])
    assert all("/sys/fs/cgroup" not in item for item in diagnosis["findings"])


def test_missing_metrics_are_unknown_not_invented():
    diagnosis = build_diagnosis(
        [{"tool": "get_memory_status", "status": "capability_missing", "data": None}],
        execution_status="environment_limited",
        security_decision="failed",
    )

    assert diagnosis["severity"] == "unknown"
    assert diagnosis["evidence"] == []
    assert "环境" in diagnosis["summary"]


def test_security_rejection_does_not_create_device_evidence():
    diagnosis = build_diagnosis(
        [],
        execution_status="blocked",
        security_decision="reject",
        security_summary="请求已阻断。",
    )

    assert diagnosis["severity"] == "unknown"
    assert diagnosis["summary"] == "请求已阻断。"
    assert diagnosis["evidence"] == []
