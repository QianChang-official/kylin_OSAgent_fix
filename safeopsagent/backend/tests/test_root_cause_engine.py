"""Tests for the cross-tool root cause analysis engine.

Covers competition scoring item 4 (intelligent root cause analysis),
including the named scenario: disk full -> locate large log -> verify
whether it is a critical database log -> safety assessment.
"""
from backend.analysis.root_cause_engine import (
    build_root_cause_chains,
    classify_large_file,
)


def _disk_result(mount: str, usage: float) -> dict:
    return {
        "tool": "disk_usage",
        "status": "success",
        "data": [{"mounted_on": mount, "use_percent": f"{usage}%", "available": "1G"}],
    }


def _large_file_result(files: list[dict]) -> dict:
    return {
        "tool": "large_file_scan",
        "status": "success",
        "data": {"files": files, "scanned_files": len(files)},
    }


def _cpu_result(usage: float, load_per_core: float) -> dict:
    return {
        "tool": "get_cpu_status",
        "status": "success",
        "data": {
            "usage_percent": usage,
            "load_per_core": load_per_core,
            "load_1m": load_per_core * 4,
            "top_processes": [],
        },
    }


def _process_result(rows: list[dict]) -> dict:
    return {
        "tool": "process_list",
        "status": "success",
        "data": rows,
    }


def _memory_result(usage_percent: float, available_mb: float) -> dict:
    return {
        "tool": "get_memory_status",
        "status": "success",
        "data": {
            "total_mb": 1000,
            "used_mb": 900,
            "available_mb": available_mb,
            "swap_total_mb": 500,
            "swap_used_mb": 10,
        },
    }


def _service_result(name: str, state: str) -> dict:
    return {
        "tool": "get_service_status",
        "status": "success",
        "data": {"service_name": name, "active_state": state},
    }


def _journal_result(rows: list[dict]) -> dict:
    return {
        "tool": "journal_query",
        "status": "success",
        "data": rows,
    }


def test_disk_pressure_with_large_files_builds_root_cause_chain():
    chains = build_root_cause_chains([
        _disk_result("/", 96.0),
        _large_file_result([
            {"path": "/var/log/nginx/access.log", "size": "5GB"},
            {"path": "/var/log/nginx/error.log", "size": "2GB"},
            {"path": "/var/lib/mysql/ibdata1", "size": "8GB"},
        ]),
    ])

    assert len(chains) == 1
    chain = chains[0]
    assert chain["chain_id"] == "disk_pressure_with_large_files"
    assert chain["symptom"] == "磁盘空间压力（/）"
    assert chain["confidence"] >= 0.8
    assert "nginx" in chain["affected_components"]
    assert chain["safety_assessment"]["cleanable_files"] == 2
    assert chain["safety_assessment"]["protected_files"] == 1
    assert chain["safety_assessment"]["database_logs_detected"] is True
    assert "/var/lib/mysql/ibdata1" in chain["safety_assessment"]["database_files"]
    assert any("safe_cleanup_plan" in action for action in chain["next_actions"])


def test_disk_pressure_without_large_files_returns_no_chain():
    chains = build_root_cause_chains([
        _disk_result("/", 96.0),
    ])
    assert chains == []


def test_disk_pressure_with_only_cleanable_logs_marks_all_cleanable():
    chains = build_root_cause_chains([
        _disk_result("/var", 90.0),
        _large_file_result([
            {"path": "/var/log/app.log", "size": "3GB"},
            {"path": "/tmp/build.tmp", "size": "1GB"},
        ]),
    ])
    assert len(chains) == 1
    chain = chains[0]
    assert chain["safety_assessment"]["cleanable_files"] == 2
    assert chain["safety_assessment"]["protected_files"] == 0
    assert chain["safety_assessment"]["database_logs_detected"] is False


def test_cpu_pressure_with_top_process_builds_chain():
    chains = build_root_cause_chains([
        _cpu_result(91.0, 1.8),
        _process_result([
            {"pid": 1234, "name": "nginx", "cpu": 78.0, "mem": 5.0},
        ]),
    ])
    assert len(chains) == 1
    chain = chains[0]
    assert chain["chain_id"] == "cpu_pressure_with_process"
    assert chain["severity"] == "warning"
    assert "nginx" in chain["root_cause"]
    assert chain["confidence"] >= 0.7


def test_cpu_pressure_without_high_process_returns_no_chain():
    chains = build_root_cause_chains([
        _cpu_result(91.0, 1.8),
        _process_result([
            {"pid": 1234, "name": "idle", "cpu": 5.0, "mem": 1.0},
        ]),
    ])
    assert chains == []


def test_memory_pressure_with_top_process_builds_chain():
    chains = build_root_cause_chains([
        _memory_result(92.0, 80.0),
        _process_result([
            {"pid": 5678, "name": "java", "cpu": 10.0, "mem": 45.0},
        ]),
    ])
    assert len(chains) == 1
    chain = chains[0]
    assert chain["chain_id"] == "memory_pressure_with_process"
    assert chain["severity"] == "critical"
    assert "java" in chain["root_cause"]


def test_service_failure_with_journal_builds_chain():
    chains = build_root_cause_chains([
        _service_result("nginx", "failed"),
        _journal_result([
            {"content": "nginx: critical error while loading", "unit": "nginx.service"},
            {"content": "failed to bind port 80", "unit": "nginx.service"},
        ]),
    ])
    assert len(chains) == 1
    chain = chains[0]
    assert chain["chain_id"] == "service_failure_with_journal"
    assert chain["severity"] == "critical"
    assert chain["confidence"] >= 0.7


def test_service_not_failed_returns_no_chain():
    chains = build_root_cause_chains([
        _service_result("nginx", "active"),
        _journal_result([{"content": "started ok", "unit": "nginx.service"}]),
    ])
    assert chains == []


def test_disk_pressure_with_journal_cross_validates():
    chains = build_root_cause_chains([
        _disk_result("/", 95.0),
        _journal_result([
            {"content": "nginx: error writing to access log", "unit": "nginx.service"},
        ]),
        _large_file_result([
            {"path": "/var/log/nginx/access.log", "size": "10GB"},
        ]),
    ])
    assert len(chains) >= 1
    disk_journal = next(
        (c for c in chains if c["chain_id"] == "disk_pressure_with_journal"), None
    )
    assert disk_journal is not None
    assert "nginx" in disk_journal["affected_components"]
    assert disk_journal["confidence"] >= 0.7


def test_multiple_chains_sorted_by_confidence():
    chains = build_root_cause_chains([
        _disk_result("/", 96.0),
        _large_file_result([{"path": "/var/log/app.log", "size": "5GB"}]),
        _cpu_result(95.0, 2.5),
        _process_result([{"pid": 1, "name": "stress", "cpu": 90.0, "mem": 2.0}]),
    ])
    assert len(chains) >= 2
    confidences = [c["confidence"] for c in chains]
    assert confidences == sorted(confidences, reverse=True)


def test_empty_results_returns_empty():
    assert build_root_cause_chains([]) == []
    assert build_root_cause_chains(None) == []


def test_classify_large_file_database_data():
    result = classify_large_file("/var/lib/mysql/ibdata1", "8GB")
    assert result["category"] == "database"
    assert result["safe_to_clean"] is False
    assert "数据库" in result["note"]


def test_classify_large_file_database_path_hint():
    result = classify_large_file("/var/log/postgresql/main.log", "2GB")
    assert result["category"] == "database"
    assert result["safe_to_clean"] is False


def test_classify_large_file_application_log():
    result = classify_large_file("/var/log/nginx/access.log", "5GB")
    assert result["category"] == "application_log"
    assert result["safe_to_clean"] is True


def test_classify_large_file_temporary():
    result = classify_large_file("/tmp/build-1234.tmp", "1GB")
    assert result["category"] == "temporary"
    assert result["safe_to_clean"] is True


def test_classify_large_file_unknown_protected_by_default():
    result = classify_large_file("/opt/app/data.bin", "500MB")
    assert result["category"] == "unknown"
    assert result["safe_to_clean"] is False


def test_build_diagnosis_includes_root_cause_chains_field():
    from backend.analysis import build_diagnosis

    diagnosis = build_diagnosis([
        _disk_result("/", 96.0),
        _large_file_result([{"path": "/var/log/nginx/access.log", "size": "5GB"}]),
    ], execution_status="success", security_decision="allow")

    assert "root_cause_chains" in diagnosis
    assert len(diagnosis["root_cause_chains"]) >= 1
    assert diagnosis["root_cause_chains"][0]["chain_id"] == "disk_pressure_with_large_files"


def test_build_diagnosis_root_cause_chains_empty_when_blocked():
    from backend.analysis import build_diagnosis

    diagnosis = build_diagnosis(
        [],
        execution_status="blocked",
        security_decision="reject",
        security_summary="blocked",
    )
    assert diagnosis["root_cause_chains"] == []


def test_virtual_filesystem_not_treated_as_disk_pressure():
    """tmpfs / devtmpfs at 100% must not be reported as real disk pressure."""
    chains = build_root_cause_chains([
        {
            "tool": "disk_usage",
            "status": "success",
            "data": [
                {"filesystem": "tmpfs", "mounted_on": "/run/user/1000", "use_percent": "100%"},
                {"filesystem": "devtmpfs", "mounted_on": "/dev", "use_percent": "100%"},
            ],
        },
        _large_file_result([{"path": "/var/log/nginx/access.log", "size": "5GB"}]),
    ])
    assert chains == []


def test_each_detector_contributes_at_most_one_chain():
    """Multiple disk rows under pressure must not duplicate the same chain."""
    chains = build_root_cause_chains([
        {
            "tool": "disk_usage",
            "status": "success",
            "data": [
                {"filesystem": "/dev/sda1", "mounted_on": "/", "use_percent": "96%"},
                {"filesystem": "/dev/sda2", "mounted_on": "/var", "use_percent": "91%"},
                {"filesystem": "/dev/sda3", "mounted_on": "/home", "use_percent": "88%"},
            ],
        },
        _large_file_result([
            {"path": "/var/log/nginx/access.log", "size": "5GB"},
            {"path": "/var/log/nginx/error.log", "size": "2GB"},
        ]),
    ])

    chain_ids = [chain["chain_id"] for chain in chains]
    assert len(chain_ids) == len(set(chain_ids))
    assert chain_ids.count("disk_pressure_with_large_files") == 1
    # All three pressured mounts are still reported inside the single chain.
    chain = chains[0]
    assert "/" in chain["affected_components"]
    assert "/var" in chain["affected_components"]
    assert "/home" in chain["affected_components"]
