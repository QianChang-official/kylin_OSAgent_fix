"""Centralized safe command execution for OS tools."""
import getpass
import os
import subprocess
import time
from pathlib import Path
from typing import Iterable, Optional

from backend import config
from backend.executor.command_spec import CommandResult


class SafeExecutor:
    def __init__(
        self,
        allowlist: Optional[Iterable[str]] = None,
        denylist: Optional[Iterable[str]] = None,
        timeout: Optional[int] = None,
        max_output_bytes: Optional[int] = None,
        max_output_lines: Optional[int] = None,
    ):
        self.allowlist = {c.lower() for c in (allowlist or config.COMMAND_WHITELIST)}
        self.denylist = {c.lower() for c in (denylist or config.COMMAND_DENYLIST)}
        self.default_timeout = timeout if timeout is not None else config.EXEC_TIMEOUT
        self.max_output_bytes = (
            max_output_bytes if max_output_bytes is not None else config.EXEC_MAX_OUTPUT_BYTES
        )
        self.max_output_lines = (
            max_output_lines if max_output_lines is not None else config.EXEC_MAX_OUTPUT_LINES
        )

    def run(self, command: list[str], timeout: Optional[int] = None) -> CommandResult:
        started = time.perf_counter()
        executor_user = self._executor_user()
        valid_command, validation_error = self._validate_command(command)
        effective_timeout = timeout if timeout is not None else self.default_timeout

        if validation_error:
            return self._result(
                False,
                None,
                "",
                "",
                valid_command,
                started,
                executor_user,
                validation_error,
            )

        try:
            completed = subprocess.run(
                valid_command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            stdout = self._truncate(completed.stdout or "")
            stderr = self._truncate(completed.stderr or "")
            return self._result(
                completed.returncode == 0,
                completed.returncode,
                stdout,
                stderr,
                valid_command,
                started,
                executor_user,
                "" if completed.returncode == 0 else stderr,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._truncate(self._coerce_output(exc.stdout))
            stderr = self._truncate(self._coerce_output(exc.stderr))
            return self._result(
                False,
                None,
                stdout,
                stderr,
                valid_command,
                started,
                executor_user,
                f"Timeout after {effective_timeout}s",
            )
        except FileNotFoundError:
            return self._result(
                False,
                None,
                "",
                "",
                valid_command,
                started,
                executor_user,
                f"Command not found: {valid_command[0]}",
            )
        except Exception as exc:
            return self._result(
                False,
                None,
                "",
                "",
                valid_command,
                started,
                executor_user,
                str(exc),
            )

    def _validate_command(self, command) -> tuple[list[str], str]:
        if isinstance(command, str):
            return [], "Command must be list[str], not string"
        if not isinstance(command, list):
            return [], "Command must be list[str]"
        if not command:
            return [], "Command list cannot be empty"

        clean_command: list[str] = []
        for part in command:
            if not isinstance(part, str):
                return clean_command, "Command arguments must all be strings"
            if part == "":
                return clean_command, "Command arguments cannot be empty"
            clean_command.append(part)

        executable = self._token_name(clean_command[0])
        if executable not in self.allowlist:
            return clean_command, f"Command not allowed: {clean_command[0]}"

        for part in clean_command:
            token_name = self._token_name(part)
            if token_name in self.denylist:
                return clean_command, f"Dangerous token blocked: {part}"
            if self._contains_shell_fragment(part):
                return clean_command, f"Shell fragment blocked in argument: {part}"

        if executable == "find":
            error = self._validate_find(clean_command)
            if error:
                return clean_command, error

        return clean_command, ""

    def _validate_find(self, command: list[str]) -> str:
        for part in command[1:]:
            lowered = part.lower()
            if lowered in {"-exec", "-execdir"}:
                return f"Unsafe find option blocked: {part}"
        return ""

    def _contains_shell_fragment(self, value: str) -> bool:
        return any(marker in value for marker in config.COMMAND_SHELL_META_CHARS)

    def _token_name(self, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            return normalized
        return Path(normalized).name

    def _truncate(self, text: str) -> str:
        if not text:
            return ""

        lines = text.splitlines()
        truncated = False
        if len(lines) > self.max_output_lines:
            text = "\n".join(lines[: self.max_output_lines])
            truncated = True

        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) > self.max_output_bytes:
            text = encoded[: self.max_output_bytes].decode("utf-8", errors="ignore")
            truncated = True

        if truncated:
            text = f"{text}\n[truncated]"
        return text

    def _coerce_output(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _executor_user(self) -> str:
        try:
            return getpass.getuser()
        except Exception:
            return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

    def _result(
        self,
        success: bool,
        returncode: Optional[int],
        stdout: str,
        stderr: str,
        command: list[str],
        started: float,
        executor_user: str,
        error: str,
    ) -> CommandResult:
        return CommandResult(
            success=success,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            command=command,
            duration_ms=int((time.perf_counter() - started) * 1000),
            executor_user=executor_user,
            error=error,
        )

