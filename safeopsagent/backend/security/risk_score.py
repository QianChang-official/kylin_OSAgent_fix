"""0-100 risk scoring for guardrail decisions."""
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class RiskScoreResult:
    score: int
    risk_level: str
    legacy_risk_level: int
    security_decision: str
    confirmation_required: bool
    blocked: bool
    matched_rules: list[str] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.score = RiskScorer.clamp_score(self.score)

    @property
    def band(self) -> str:
        return self.risk_level


class RiskScorer:
    """Convert layered guardrail checks into a 0-100 score.

    The legacy 1-5 risk level is kept for database compatibility. The 0-100
    score is used in API responses and decision explanations.
    """

    LEVEL_BASE_SCORE: ClassVar[dict[int, int]] = {
        1: 10,
        2: 30,
        3: 50,
        4: 70,
        5: 95,
    }

    TOOL_BASE_SCORE: ClassVar[dict[str, int]] = {
        "get_memory_status": 10,
        "disk_usage": 12,
        "process_list": 16,
        "get_port_usage": 18,
        "network_status": 20,
        "journal_query": 22,
        "get_service_status": 25,
        "large_file_scan": 40,
        "get_cpu_status": 14,
        "config_drift_check": 20,
        "zombie_process_check": 16,
        "disk_io_analysis": 14,
        "impact_analysis": 22,
        "safe_cleanup_scan": 30,
        "safe_cleanup_plan": 40,
        "safe_cleanup_quarantine": 75,
        "safe_cleanup_restore": 75,
    }

    RULE_WEIGHTS: ClassVar[dict[str, int]] = {
        "delete_command": 100,
        "dangerous_cmd": 100,
        "shell_injection_char": 100,
        "tool_not_in_whitelist": 100,
        "schema_validation": 100,
        "dangerous_path_in_arg": 75,
        "dangerous_path": 70,
        "output_contains_delete_cmd": 70,
        "injection_template": 65,
        "output_injection": 60,
        "protected_credential": 100,
        "path_traversal": 100,
    }

    def score(
        self,
        *,
        input_check: Any | None = None,
        tool_check: Any | None = None,
        arg_check: Any | None = None,
        output_check: Any | None = None,
        tool_name: str = "",
        arguments: dict | None = None,
        extra_factors: list[str] | None = None,
    ) -> RiskScoreResult:
        checks = [check for check in [input_check, tool_check, arg_check, output_check] if check is not None]
        factors: list[str] = []
        matched_rules: list[str] = []
        base_scores = [self.LEVEL_BASE_SCORE.get(getattr(check, "risk_level", 1), 10) for check in checks]
        score = max(base_scores or [10])

        if tool_name:
            if tool_name not in self.TOOL_BASE_SCORE:
                tool_base = 100
                matched_rules.append(f"unclassified_tool:{tool_name}")
                factors.append(f"unclassified_tool:{tool_name}:100")
            else:
                tool_base = self.TOOL_BASE_SCORE[tool_name]
            if tool_base > score:
                factors.append(f"tool_base:{tool_name}:{tool_base}")
            score = max(score, tool_base)

        for check in checks:
            for hit in getattr(check, "rule_hits", []) or []:
                matched_rules.append(hit)
                weight = self._weight_for_hit(hit)
                if weight:
                    factors.append(f"rule:{hit}:{weight}")
                    score = max(score, weight)

            if getattr(check, "passed", True) is False:
                score = max(score, 100)
                factors.append(f"blocked_check:{getattr(check, 'channel', 'unknown')}")

        if arguments:
            score = max(score, self._argument_score(arguments, factors))

        for factor in extra_factors or []:
            factors.append(factor)
            matched_rules.append(factor)
            if factor.startswith("schema_validation"):
                score = max(score, 100)
            elif factor.startswith("tool_not_found"):
                score = max(score, 100)

        score = self.clamp_score(score)
        failed_check = any(getattr(check, "passed", True) is False for check in checks)
        security_decision = self._score_to_decision(score, failed_check)
        risk_level = self._score_to_level(score)
        return RiskScoreResult(
            score=score,
            risk_level=risk_level,
            legacy_risk_level=self._score_to_legacy_level(score),
            security_decision=security_decision,
            confirmation_required=security_decision == "confirm",
            blocked=security_decision == "reject",
            matched_rules=matched_rules,
            factors=factors,
        )

    def _weight_for_hit(self, hit: str) -> int:
        for prefix, weight in self.RULE_WEIGHTS.items():
            if hit.startswith(prefix) or f":{prefix}" in hit:
                return weight
        return 0

    def _argument_score(self, arguments: dict, factors: list[str]) -> int:
        score = 10
        for key, value in arguments.items():
            if isinstance(value, str):
                if len(value) > 512:
                    score = max(score, 50)
                    factors.append(f"long_argument:{key}")
                if any(token in value for token in [";", "|", "&", "`", "$", "\n", "\r"]):
                    score = max(score, 100)
                    factors.append(f"shell_meta_argument:{key}")
            elif isinstance(value, (list, dict)):
                score = max(score, 35)
                factors.append(f"nested_argument:{key}")
        return score

    def _score_to_level(self, score: int) -> str:
        if score >= 100:
            return "forbidden"
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _score_to_legacy_level(self, score: int) -> int:
        if score >= 100:
            return 5
        if score >= 70:
            return 4
        if score >= 40:
            return 3
        if score >= 20:
            return 2
        return 1

    def _score_to_decision(self, score: int, failed_check: bool) -> str:
        if failed_check or score >= 100:
            return "reject"
        if score >= 70:
            return "confirm"
        return "allow"

    @staticmethod
    def clamp_score(score: Any) -> int:
        try:
            value = int(score)
        except (TypeError, ValueError):
            value = 0
        return max(0, min(100, value))
