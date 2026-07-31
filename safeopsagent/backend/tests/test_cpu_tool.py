
from backend.executor.command_spec import CommandResult
from backend.tools import cpu_tool


def _command_result(success=True, stdout="", error=""):
    return CommandResult(
        success=success,
        returncode=0 if success else 1,
        stdout=stdout,
        stderr="",
        command=["ps"],
        executor_user="tester",
        error=error,
    )


def test_cpu_tool_returns_real_sampled_fields(monkeypatch, tmp_path):
    stat_path = tmp_path / "stat"
    load_path = tmp_path / "loadavg"
    info_path = tmp_path / "cpuinfo"
    stat_path.write_text("cpu  100 0 100 800 0 0 0 0\n", encoding="utf-8")
    load_path.write_text("1.20 0.80 0.40 1/100 1\n", encoding="utf-8")
    info_path.write_text(
        "processor: 0\nphysical id: 0\ncore id: 0\n\n"
        "processor: 1\nphysical id: 0\ncore id: 1\n",
        encoding="utf-8",
    )
    samples = iter([(1000, 800), (1100, 850)])
    monkeypatch.setattr(cpu_tool, "PROC_STAT", stat_path)
    monkeypatch.setattr(cpu_tool, "PROC_LOADAVG", load_path)
    monkeypatch.setattr(cpu_tool, "PROC_CPUINFO", info_path)
    monkeypatch.setattr(cpu_tool, "_read_cpu_times", lambda text: next(samples))
    monkeypatch.setattr(cpu_tool.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        cpu_tool._executor,
        "run",
        lambda command: _command_result(
            stdout="PID USER COMMAND %CPU %MEM\n12 root worker 82.5 1.0\n"
        ),
    )

    result = cpu_tool._get_cpu_status()

    assert result.status == "success"
    assert result.data["usage_percent"] == 50.0
    assert result.data["usage_sample_kind"] == "instantaneous"
    assert result.data["sample_interval_seconds"] == 1.0
    assert result.data["logical_cores"] == 2
    assert result.data["physical_cores"] == 2
    assert result.data["load_per_core"] == 0.6
    assert result.data["top_processes"][0]["name"] == "worker"


def test_cpu_tool_non_linux_is_environment_limited(monkeypatch, tmp_path):
    missing = tmp_path / "missing"
    monkeypatch.setattr(cpu_tool, "PROC_STAT", missing)
    monkeypatch.setattr(cpu_tool, "PROC_LOADAVG", missing)
    monkeypatch.setattr(cpu_tool, "PROC_CPUINFO", missing)

    result = cpu_tool._get_cpu_status()

    assert result.status == "capability_missing"
    assert result.data["status"] == "environment_limited"
    assert result.data["usage_percent"] is None
    assert result.data["usage_sample_kind"] == "instantaneous"


def test_cpuinfo_loongarch_shape_does_not_invent_physical_cores():
    logical, physical = cpu_tool._parse_cpuinfo(
        "processor : 0\nmodel name : Loongson\n\n"
        "processor : 1\nmodel name : Loongson\n"
    )

    assert logical == 2
    assert physical is None


def test_cpu_sample_refuses_zero_delta():
    try:
        cpu_tool._usage_percent((100, 80), (100, 80))
    except ValueError as exc:
        assert "no measurable delta" in str(exc)
    else:
        raise AssertionError("zero-delta CPU sample must not become a fake 0%")


def test_cpu_times_do_not_double_count_guest_ticks():
    total, idle = cpu_tool._read_cpu_times(
        "cpu  100 20 30 800 10 5 4 3 40 2\n"
    )

    assert total == 972
    assert idle == 810
