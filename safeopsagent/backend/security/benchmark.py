"""Repeatable, data-driven security benchmark runner."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from backend import app as app_module
from backend.cleanup.service import CleanupError, CleanupService
from backend.security.guardrail import Guardrail


DEFAULT_CASES = Path(__file__).resolve().parents[2] / "tests" / "data" / "security_benchmark_cases.json"


def run_security_benchmark(cases_path: str | Path = DEFAULT_CASES) -> dict[str, Any]:
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("Security benchmark cases must be a JSON array")

    results = []
    for case in cases:
        actual_blocked, detail = _evaluate_case(case)
        expected_blocked = case.get("kind") == "attack"
        skipped = actual_blocked is None
        passed = None if skipped else actual_blocked == expected_blocked
        results.append({
            "id": case.get("id"),
            "category": case.get("category"),
            "kind": case.get("kind"),
            "passed": passed,
            "skipped": skipped,
            "actual_blocked": actual_blocked,
            "detail": detail,
        })

    evaluated = [item for item in results if not item["skipped"]]
    attack_results = [item for item in evaluated if item["kind"] == "attack"]
    normal_results = [item for item in evaluated if item["kind"] == "normal"]
    blocked_attacks = sum(item["actual_blocked"] for item in attack_results)
    allowed_normal = sum(not item["actual_blocked"] for item in normal_results)
    categories: dict[str, dict[str, int | float]] = {}
    for item in results:
        bucket = categories.setdefault(
            str(item["category"]),
            {
                "total": 0,
                "evaluated": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "pass_rate": 0.0,
            },
        )
        bucket["total"] += 1
        if item["skipped"]:
            bucket["skipped"] += 1
        else:
            bucket["evaluated"] += 1
            bucket["passed" if item["passed"] else "failed"] += 1
    for bucket in categories.values():
        denominator = bucket["evaluated"]
        bucket["pass_rate"] = (
            round(bucket["passed"] / denominator * 100, 2)
            if denominator
            else 0.0
        )

    passed_count = sum(item["passed"] is True for item in evaluated)
    return {
        "total_cases": len(results),
        "evaluated_cases": len(evaluated),
        "skipped_cases": len(results) - len(evaluated),
        "attack_cases": len(attack_results),
        "normal_cases": len(normal_results),
        "blocked_attack_cases": blocked_attacks,
        "allowed_normal_cases": allowed_normal,
        "false_positive": len(normal_results) - allowed_normal,
        "false_negative": len(attack_results) - blocked_attacks,
        "pass_rate": round(passed_count / len(evaluated) * 100, 2) if evaluated else 0.0,
        "category_results": categories,
        "cases": results,
    }


def _evaluate_case(case: dict[str, Any]) -> tuple[bool | None, str]:
    channel = case.get("channel", "input")
    guardrail = Guardrail()
    if channel == "input":
        check = guardrail.check_input(str(case.get("payload", "")))
        return not check.passed, ",".join(check.rule_hits)
    if channel == "tool_args":
        check = guardrail.validate_tool_args(
            str(case.get("tool_name", "large_file_scan")),
            case.get("arguments") if isinstance(case.get("arguments"), dict) else {},
        )
        return not check.passed, ",".join(check.rule_hits)
    if channel == "output":
        check = guardrail.check_tool_output(str(case.get("payload", "")))
        return not check.passed, ",".join(check.rule_hits)
    if channel == "cleanup":
        return _evaluate_cleanup(str(case.get("scenario", "")))
    if channel == "confirmation":
        return _evaluate_confirmation(str(case.get("scenario", "")))
    raise ValueError(f"Unknown benchmark channel: {channel}")


def _evaluate_cleanup(scenario: str) -> tuple[bool | None, str]:
    with tempfile.TemporaryDirectory(prefix="safeops-benchmark-") as temp:
        base = Path(temp)
        allowed = base / "allowed"
        outside = base / "outside"
        allowed.mkdir()
        outside.mkdir()
        service = CleanupService(allowed_roots=(allowed,))
        old = time.time() - 48 * 3600

        if scenario == "allowed":
            candidate = allowed / "old.tmp"
            candidate.write_text("safe", encoding="utf-8")
            os.utime(candidate, (old, old))
            result = service.scan(str(allowed))
            return result["candidate_count"] == 0, "allowed candidate scan"
        if scenario in {"outside", "traversal"}:
            requested = outside if scenario == "outside" else allowed / ".." / "outside"
            try:
                service.scan(str(requested))
            except CleanupError as exc:
                return True, str(exc)
            return False, "outside cleanup path was accepted"
        if scenario == "symlink":
            target = outside / "secret.tmp"
            target.write_text("secret", encoding="utf-8")
            os.utime(target, (old, old))
            link = allowed / "link.tmp"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                return None, f"skipped: platform refused symlink setup: {exc}"
            result = service.scan(str(allowed))
            return result["candidate_count"] == 0, "symlink candidate rejected"
        if scenario == "hardlink":
            target = allowed / "source.tmp"
            target.write_text("linked", encoding="utf-8")
            os.utime(target, (old, old))
            try:
                os.link(target, allowed / "copy.tmp")
            except OSError as exc:
                return None, f"skipped: platform refused hardlink setup: {exc}"
            result = service.scan(str(allowed))
            return result["candidate_count"] == 0, "hard-linked candidates rejected"
    return False, "unknown cleanup scenario"


def _evaluate_confirmation(scenario: str) -> tuple[bool, str]:
    token = f"benchmark-{scenario}"
    now = time.time()
    if scenario == "invalid":
        app_module._confirmations.pop(token, None)
    else:
        app_module._confirmations[token] = {
            "original_request_id": "benchmark",
            "tool_name": "get_memory_status",
            "arguments": {},
            "risk_score": 70,
            "risk_level": "high",
            "legacy_risk_level": 4,
            "risk_factors": [],
            "matched_rules": [],
            "security_decision": "confirm",
            "security_reason": "confirmation_required",
            "rule_hits": {},
            "session_id": "security-benchmark",
            "used": scenario == "used",
            "expires_at": now - 1 if scenario == "expired" else now + 60,
        }
    class _BenchmarkLogger:
        def log(self, entry):
            return True

    original_get_logger = app_module.get_logger
    try:
        app_module.get_logger = lambda: _BenchmarkLogger()
        response = app_module.confirm_tool(
            app_module.ToolConfirmRequest(
                confirmation_token=token,
                session_id="security-benchmark",
            )
        )
        return response.get("success") is False, str(response.get("security_reason", ""))
    finally:
        app_module.get_logger = original_get_logger
        app_module._confirmations.pop(token, None)
