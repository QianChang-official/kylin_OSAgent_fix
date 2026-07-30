from pathlib import Path

import pytest

import backend.executor.safe_executor as safe_executor_module
from backend.executor import SafeExecutor
from backend.tools.large_file_scan import _large_file_scan


class FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_rejects_string_command():
    result = SafeExecutor().run("ps aux")  # type: ignore[arg-type]

    assert not result.success
    assert result.returncode is None
    assert "list[str]" in result.error


def test_rejects_non_allowlisted_command():
    result = SafeExecutor().run(["python", "--version"])

    assert not result.success
    assert "not allowed" in result.error


def test_rejects_dangerous_token_anywhere():
    result = SafeExecutor().run(["find", "/var/log", "-type", "f", "rm"])

    assert not result.success
    assert "Dangerous token" in result.error


def test_rejects_find_exec_options():
    executor = SafeExecutor()

    result = executor.run(["find", "/var/log", "-type", "f", "-execdir", "du", "{}", "+"])

    assert not result.success
    assert "find option" in result.error


def test_executor_sets_safe_subprocess_options(monkeypatch):
    captured = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeCompleted(stdout="ok\n")

    monkeypatch.setattr(safe_executor_module.subprocess, "run", fake_runner)

    result = SafeExecutor(timeout=7).run(["ps", "aux"])

    assert result.success
    assert result.stdout == "ok\n"
    assert captured["command"] == ["ps", "aux"]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["timeout"] == 7
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True


def test_output_is_truncated(monkeypatch):
    def fake_runner(command, **kwargs):
        return FakeCompleted(stdout="line1\nline2\nline3\n")

    monkeypatch.setattr(safe_executor_module.subprocess, "run", fake_runner)

    result = SafeExecutor(max_output_lines=1, max_output_bytes=100).run(["ps", "aux"])

    assert result.success
    assert result.stdout == "line1\n[truncated]"


def test_timeout_returns_structured_result(monkeypatch):
    def fake_runner(command, **kwargs):
        raise safe_executor_module.subprocess.TimeoutExpired(
            cmd=command,
            timeout=kwargs["timeout"],
            output="partial",
            stderr="timeout",
        )

    monkeypatch.setattr(safe_executor_module.subprocess, "run", fake_runner)

    result = SafeExecutor(timeout=3).run(["ps", "aux"])

    assert not result.success
    assert result.returncode is None
    assert result.stdout == "partial"
    assert result.stderr == "timeout"
    assert "Timeout after 3s" == result.error


def test_executor_user_is_present(monkeypatch):
    def fake_runner(command, **kwargs):
        return FakeCompleted(stdout="ok")

    monkeypatch.setattr(safe_executor_module.subprocess, "run", fake_runner)

    result = SafeExecutor().run(["ps", "aux"])

    assert result.executor_user


def test_large_file_scan_blocks_sensitive_roots():
    for path in ["/", "/etc", "/boot", "/dev", "/proc", "/sys", "/run"]:
        result = _large_file_scan(path=path, size="+1K")

        assert result.status == "command_failed"
        assert "blocked" in result.error.lower()


def test_large_file_scan_skips_symlink(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (target / "secret.log").write_text("x" * 4096, encoding="utf-8")
    link = allowed / "link"

    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available in this environment")

    monkeypatch.setattr("backend.config.LARGE_FILE_SCAN_ALLOWED_ROOTS", (str(allowed),))
    monkeypatch.setattr("backend.config.LARGE_FILE_SCAN_BLOCKED_ROOTS", ("/", "/etc", "/proc", "/sys", "/dev"))

    result = _large_file_scan(path=str(allowed), size="+1K")

    assert result.status in {"success", "no_output"}
    files = result.data.get("files", []) if isinstance(result.data, dict) else []
    warnings = result.data.get("warnings", []) if isinstance(result.data, dict) else []
    assert not any(Path(item["path"]).name == "secret.log" for item in files)
    assert any("symlink" in warning.lower() for warning in warnings)

