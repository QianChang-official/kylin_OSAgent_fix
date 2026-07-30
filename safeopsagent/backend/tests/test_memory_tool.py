from backend.executor.command_spec import CommandResult
from backend.tools import memory_tool


def _result(success=True, stdout="", stderr="", error="", command=None):
    return CommandResult(
        success=success,
        returncode=0 if success else 1,
        stdout=stdout,
        stderr=stderr,
        command=command or [],
        duration_ms=1,
        executor_user="tester",
        error=error,
    )


def test_get_memory_status_parses_free_output(monkeypatch):
    output = (
        "               total        used        free      shared  buff/cache   available\n"
        "Mem:           16000        8000        2000         100        6000        7000\n"
        "Swap:           2048         256        1792\n"
    )
    monkeypatch.setattr(memory_tool._executor, "run", lambda command: _result(stdout=output, command=command))

    result = memory_tool._get_memory_status()

    assert result.status == "success"
    assert result.data["total_mb"] == 16000
    assert result.data["used_mb"] == 8000
    assert result.data["available_mb"] == 7000
    assert result.data["swap_total_mb"] == 2048
    assert result.data["swap_used_mb"] == 256


def test_get_memory_status_handles_missing_free(monkeypatch):
    monkeypatch.setattr(
        memory_tool._executor,
        "run",
        lambda command: _result(False, error="Command not found: free", command=command),
    )

    result = memory_tool._get_memory_status()

    assert result.status == "capability_missing"


def test_get_memory_status_parse_warning(monkeypatch):
    monkeypatch.setattr(memory_tool._executor, "run", lambda command: _result(stdout="bad output", command=command))

    result = memory_tool._get_memory_status()

    assert result.status == "parse_warning"
    assert "Mem line not found" in result.error

