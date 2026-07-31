#!/usr/bin/env python3
"""Compatibility smoke checks for SafeOpsAgent on Kylin V11/Linux.

The script is intentionally read-mostly. It does not start or stop services,
does not modify system configuration, and does not execute destructive
commands. The only write check appends one clearly marked audit record.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
HTTP_TIMEOUT_SECONDS = 3
REQUIRED_COMMANDS = [
    "ss",
    "lsof",
    "netstat",
    "ps",
    "df",
    "free",
    "systemctl",
    "journalctl",
]


class CheckRunner:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.checks: list[dict[str, Any]] = []
        self.backend_running = False

    def add(self, name: str, status: str, detail: str, suggestion: str = ""):
        self.checks.append(
            {
                "name": name,
                "status": status,
                "detail": detail,
                "suggestion": suggestion,
            }
        )

    def run(self) -> dict[str, Any]:
        self._check_python()
        self._check_os()
        self._check_architecture()
        self._check_commands()
        self._check_backend_import()
        self._check_safe_executor()
        self._check_audit_write()
        self._check_http_endpoints()
        return self._result()

    def _check_python(self):
        version = sys.version_info
        detail = platform.python_version()
        if version >= (3, 10):
            self.add("python_version", "pass", detail)
        else:
            self.add(
                "python_version",
                "fail",
                detail,
                "Use Python 3.10+; Python 3.11 is recommended for the demo.",
            )

    def _check_os(self):
        detail = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
        }
        self.add("os_info", "pass", json.dumps(detail, ensure_ascii=False))

    def _check_architecture(self):
        detail = platform.machine() or "unknown"
        self.add("cpu_architecture", "pass", detail)

    def _check_commands(self):
        for command in REQUIRED_COMMANDS:
            path = shutil.which(command)
            if path:
                self.add(f"command:{command}", "pass", path)
            else:
                self.add(
                    f"command:{command}",
                    "warn",
                    "not found in PATH",
                    "Install the related system package if this tool is needed; core demo can degrade gracefully.",
                )

    def _check_backend_import(self):
        try:
            _ensure_project_on_path()
            os.environ.setdefault("LLM_PROVIDER", "mock")
            import backend.app  # noqa: F401

            self.add("backend_import", "pass", "import backend.app succeeded")
        except Exception as exc:
            self.add(
                "backend_import",
                "fail",
                _short_error(exc),
                "Run from the safeopsagent project root and set PYTHONPATH to the project root.",
            )

    def _check_safe_executor(self):
        try:
            _ensure_project_on_path()
            from backend.executor import SafeExecutor

            result = SafeExecutor(timeout=HTTP_TIMEOUT_SECONDS).run(["whoami"], timeout=HTTP_TIMEOUT_SECONDS)
            detail = {
                "success": result.success,
                "returncode": result.returncode,
                "executor_user": result.executor_user,
                "error": result.error,
            }
            status = "pass" if result.success else "fail"
            suggestion = "" if result.success else "Check that the whoami command is available and executable."
            self.add("safe_executor_basic", status, json.dumps(detail, ensure_ascii=False), suggestion)
        except Exception as exc:
            self.add(
                "safe_executor_basic",
                "fail",
                _short_error(exc),
                "SafeExecutor import or execution failed; check backend dependencies.",
            )

    def _check_audit_write(self):
        try:
            _ensure_project_on_path()
            from backend.audit.logger import get_logger

            request_id = f"compatibility_check-{int(time.time())}"
            ok = get_logger().log(
                {
                    "session_id": "compatibility_check",
                    "request_id": request_id,
                    "user_input": "compatibility_check audit writable probe",
                    "intent": "compatibility_check",
                    "selected_tool": "",
                    "tool_arguments": {},
                    "risk_level": 1,
                    "risk_score": 10,
                    "risk_level_text": "low",
                    "legacy_risk_level": 1,
                    "security_decision": "allow",
                    "security_reason": "compatibility_check",
                    "matched_rules": [],
                    "confirmation_required": False,
                    "executed": False,
                    "actual_command": [],
                    "executor_user": "",
                    "execution_success": False,
                    "execution_result": {"status": "compatibility_check"},
                    "stdout_summary": "",
                    "stderr_summary": "",
                    "final_response": "compatibility_check audit writable probe",
                    "rule_hits": [],
                    "duration_ms": 0,
                }
            )
            if ok:
                self.add("sqlite_audit_writable", "pass", f"appended audit record {request_id}")
            else:
                self.add(
                    "sqlite_audit_writable",
                    "fail",
                    "AuditLogger.log returned False",
                    "Check data directory permissions and SQLite file locks.",
                )
        except Exception as exc:
            self.add(
                "sqlite_audit_writable",
                "fail",
                _short_error(exc),
                "Check data directory permissions and SQLite availability.",
            )

    def _check_http_endpoints(self):
        health = self._http_json("GET", "/health")
        if not health["ok"]:
            self.add(
                "http:/health",
                "skip" if health["connection_error"] else "fail",
                health["detail"],
                "Start backend first: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000",
            )
            self._skip_http_dependents()
            return

        self.backend_running = True
        self.add("http:/health", "pass", _compact_json(health["data"]))
        self._check_tools_list()
        self._check_tools_call_memory()
        self._check_chat_mock()
        self._check_dangerous_rejection()
        self._check_audit_logs()

    def _check_tools_list(self):
        response = self._http_json("GET", "/tools/list")
        if not response["ok"]:
            self.add("http:/tools/list", "fail", response["detail"], "Check backend logs.")
            return
        tools = response["data"].get("tools", [])
        if isinstance(tools, list) and tools:
            self.add("http:/tools/list", "pass", f"{len(tools)} tools registered")
        else:
            self.add("http:/tools/list", "fail", _compact_json(response["data"]), "Tool registry is empty.")

    def _check_tools_call_memory(self):
        response = self._http_json(
            "POST",
            "/tools/call",
            {"tool_name": "get_memory_status", "arguments": {}, "session_id": "compatibility_check"},
        )
        if not response["ok"]:
            self.add("http:/tools/call:get_memory_status", "fail", response["detail"], "Check backend logs.")
            return
        data = response["data"]
        if data.get("success") is True:
            self.add("http:/tools/call:get_memory_status", "pass", _compact_json(data))
        else:
            self.add(
                "http:/tools/call:get_memory_status",
                "warn",
                _compact_json(data),
                "If running on Windows or a minimal image, install/provide the free command; Kylin should include it.",
            )

    def _check_chat_mock(self):
        response = self._http_json(
            "POST",
            "/chat",
            {"session_id": "compatibility_check", "message": "看看系统内存情况"},
        )
        if not response["ok"]:
            self.add(
                "http:/chat:mock",
                "fail",
                response["detail"],
                "Start backend with LLM_PROVIDER=mock before running this check.",
            )
            return
        data = response["data"]
        if "request_id" in data and "security_decision" in data:
            self.add("http:/chat:mock", "pass", _compact_json(data))
        else:
            self.add(
                "http:/chat:mock",
                "warn",
                _compact_json(data),
                "Response shape is unexpected; confirm backend is using the current branch.",
            )

    def _check_dangerous_rejection(self):
        response = self._http_json(
            "POST",
            "/chat",
            {"session_id": "compatibility_check", "message": "帮我 rm -rf /"},
        )
        if not response["ok"]:
            self.add("http:/chat:dangerous_rejection", "fail", response["detail"], "Check backend logs.")
            return
        data = response["data"]
        rejected = (
            data.get("security_decision") == "reject"
            or data.get("risk_level") == "forbidden"
            or data.get("legacy_risk_level") == 5
        )
        if rejected and not data.get("executed"):
            self.add("http:/chat:dangerous_rejection", "pass", _compact_json(data))
        else:
            self.add(
                "http:/chat:dangerous_rejection",
                "fail",
                _compact_json(data),
                "Guardrail should reject rm -rf / without executing any tool.",
            )

    def _check_audit_logs(self):
        response = self._http_json("GET", "/audit/logs?session_id=compatibility_check&limit=5")
        if not response["ok"]:
            self.add("http:/audit/logs", "fail", response["detail"], "Check backend logs.")
            return
        logs = response["data"].get("logs", [])
        if isinstance(logs, list):
            self.add("http:/audit/logs", "pass", f"{len(logs)} recent compatibility_check logs readable")
        else:
            self.add("http:/audit/logs", "fail", _compact_json(response["data"]), "Unexpected audit response shape.")

    def _skip_http_dependents(self):
        for name in [
            "http:/tools/list",
            "http:/tools/call:get_memory_status",
            "http:/chat:mock",
            "http:/chat:dangerous_rejection",
            "http:/audit/logs",
        ]:
            self.add(
                name,
                "skip",
                "backend service is not reachable",
                f"Start backend at {self.base_url} and rerun this script.",
            )

    def _http_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body else {}
                return {"ok": True, "data": parsed, "detail": "", "connection_error": False}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return {
                "ok": False,
                "data": {},
                "detail": f"HTTP {exc.code}: {body[:300]}",
                "connection_error": False,
            }
        except (urllib.error.URLError, TimeoutError) as exc:
            return {
                "ok": False,
                "data": {},
                "detail": _short_error(exc),
                "connection_error": True,
            }
        except Exception as exc:
            return {
                "ok": False,
                "data": {},
                "detail": _short_error(exc),
                "connection_error": False,
            }

    def _result(self) -> dict[str, Any]:
        counts = {status: 0 for status in ["pass", "warn", "fail", "skip"]}
        for check in self.checks:
            counts[check["status"]] = counts.get(check["status"], 0) + 1
        overall = "fail" if counts["fail"] else "warn" if counts["warn"] or counts["skip"] else "pass"
        return {
            "summary": {
                "overall": overall,
                "counts": counts,
                "base_url": self.base_url,
                "http_timeout_seconds": self.timeout,
            },
            "environment": {
                "project_root": str(PROJECT_ROOT),
                "python": platform.python_version(),
                "os": platform.platform(),
                "architecture": platform.machine(),
                "llm_provider_note": "HTTP /chat checks require the already-started backend to use LLM_PROVIDER=mock.",
            },
            "checks": self.checks,
        }


def _ensure_project_on_path():
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _short_error(exc: BaseException) -> str:
    message = f"{exc.__class__.__name__}: {exc}"
    if len(message) > 300:
        message = message[:297] + "..."
    return message


def _compact_json(value: Any, limit: int = 500) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _print_table(result: dict[str, Any]):
    print(f"Overall: {result['summary']['overall']}")
    print(f"Base URL: {result['summary']['base_url']}")
    print(f"Timeout: {result['summary']['http_timeout_seconds']}s")
    print("")
    print(f"{'STATUS':<6} {'CHECK':<38} DETAIL")
    print("-" * 90)
    for check in result["checks"]:
        detail = check["detail"].replace("\n", " ")
        if len(detail) > 70:
            detail = detail[:67] + "..."
        print(f"{check['status']:<6} {check['name']:<38} {detail}")
        if check.get("suggestion"):
            suggestion = check["suggestion"].replace("\n", " ")
            if len(suggestion) > 78:
                suggestion = suggestion[:75] + "..."
            print(f"{'':<6} {'suggestion':<38} {suggestion}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SafeOpsAgent Kylin compatibility smoke check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Already-running backend base URL")
    parser.add_argument("--timeout", type=float, default=HTTP_TIMEOUT_SECONDS, help="HTTP timeout seconds")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print structured JSON output")
    output.add_argument("--table", action="store_true", help="Print a compact table")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timeout = max(1.0, min(float(args.timeout), 5.0))
    os.environ.setdefault("LLM_PROVIDER", "mock")
    runner = CheckRunner(args.base_url, timeout)
    try:
        result = runner.run()
    except Exception as exc:
        result = {
            "summary": {
                "overall": "fail",
                "counts": {"pass": 0, "warn": 0, "fail": 1, "skip": 0},
                "base_url": args.base_url,
                "http_timeout_seconds": timeout,
            },
            "environment": {
                "project_root": str(PROJECT_ROOT),
                "python": platform.python_version(),
                "os": platform.platform(),
                "architecture": platform.machine(),
            },
            "checks": [
                {
                    "name": "compatibility_check_script",
                    "status": "fail",
                    "detail": _short_error(exc),
                    "suggestion": traceback.format_exc(limit=1),
                }
            ],
        }

    if args.table:
        _print_table(result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["summary"]["overall"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
