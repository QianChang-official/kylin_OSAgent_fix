from backend.executor.command_spec import CommandResult
from backend.tools import port_tool


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


def test_get_port_usage_parses_ss(monkeypatch):
    output = (
        "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
        'LISTEN 0 128 0.0.0.0:8080 0.0.0.0:* users:(("python",pid=1234,fd=3))\n'
    )
    monkeypatch.setattr(port_tool._executor, "run", lambda command: _result(stdout=output, command=command))

    result = port_tool._get_port_usage(8080)

    assert result.status == "success"
    assert result.data["port"] == 8080
    assert result.data["listeners"][0]["pid"] == "1234"
    assert result.data["listeners"][0]["process"] == "python"


def test_get_port_usage_rejects_invalid_ports():
    for value in [0, 65536, "8080", "8080; rm -rf /", True]:
        result = port_tool._get_port_usage(value)  # type: ignore[arg-type]

        assert result.status == "command_failed"


def test_get_port_usage_falls_back_to_lsof(monkeypatch):
    calls = []
    lsof_output = (
        "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
        "nginx 222 root 6u IPv4 12345 0t0 TCP *:8080 (LISTEN)\n"
    )

    def fake_run(command):
        calls.append(command[0])
        if command[0] == "ss":
            return _result(False, error="Command not found: ss", command=command)
        return _result(stdout=lsof_output, command=command)

    monkeypatch.setattr(port_tool._executor, "run", fake_run)

    result = port_tool._get_port_usage(8080)

    assert calls[:2] == ["ss", "lsof"]
    assert result.status == "success"
    assert result.data["listeners"][0]["pid"] == "222"
    assert result.data["listeners"][0]["process"] == "nginx"

