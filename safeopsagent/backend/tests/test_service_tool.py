from backend.executor.command_spec import CommandResult
from backend.tools import service_tool


def _result(success=True, stdout="", stderr="", error="", command=None, returncode=None):
    return CommandResult(
        success=success,
        returncode=(0 if success else 1) if returncode is None else returncode,
        stdout=stdout,
        stderr=stderr,
        command=command or [],
        duration_ms=1,
        executor_user="tester",
        error=error,
    )


def test_get_service_status_parses_active_service(monkeypatch):
    def fake_run(command):
        if command[:2] == ["systemctl", "is-active"]:
            return _result(stdout="active\n", command=command)
        if command[:2] == ["systemctl", "is-enabled"]:
            return _result(stdout="enabled\n", command=command)
        return _result(stdout="● nginx.service - nginx\n   Active: active (running)\n", command=command)

    monkeypatch.setattr(service_tool._executor, "run", fake_run)

    result = service_tool._get_service_status("nginx.service")

    assert result.status == "success"
    assert result.data["service_name"] == "nginx.service"
    assert result.data["active_state"] == "active"
    assert result.data["enabled_state"] == "enabled"
    assert "Active: active" in result.data["status_summary"]


def test_get_service_status_rejects_invalid_name():
    for name in ["", "bad name", "nginx;reboot", "nginx|cat", "x" * 65, "nginx\n"]:
        result = service_tool._get_service_status(name)

        assert result.status == "command_failed"


def test_get_service_status_handles_missing_service(monkeypatch):
    def fake_run(command):
        if command[:2] == ["systemctl", "is-active"]:
            return _result(False, stdout="inactive\n", error="inactive", command=command, returncode=3)
        if command[:2] == ["systemctl", "is-enabled"]:
            return _result(False, stdout="disabled\n", error="disabled", command=command, returncode=1)
        return _result(False, stderr="Unit nginx.service could not be found.\n", error="unit not found", command=command)

    monkeypatch.setattr(service_tool._executor, "run", fake_run)

    result = service_tool._get_service_status("nginx")

    assert result.status == "command_failed"
    assert result.data["service_name"] == "nginx"
    assert result.data["active_state"] == "inactive"
    assert "could not be found" in result.data["raw_output"]


def test_get_service_status_handles_missing_systemctl(monkeypatch):
    monkeypatch.setattr(
        service_tool._executor,
        "run",
        lambda command: _result(False, error="Command not found: systemctl", command=command),
    )

    result = service_tool._get_service_status("nginx")

    assert result.status == "capability_missing"
    assert result.error == "systemctl not available"
