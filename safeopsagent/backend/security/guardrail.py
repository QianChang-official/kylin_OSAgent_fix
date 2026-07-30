"""Security guardrail — multi-layer input/output validation and risk scoring."""
import re
import unicodedata
from urllib.parse import unquote
from dataclasses import dataclass, field
from typing import List, Optional
from backend import config
from backend.security.risk_score import RiskScorer, RiskScoreResult


@dataclass
class SecurityCheck:
    passed: bool
    risk_level: int  # 1-5
    rule_hits: List[str] = field(default_factory=list)
    details: str = ""
    channel: str = "user_input"  # user_input | tool_output


class Guardrail:
    """10-layer security guardrail."""

    COMMAND_TOKEN_CHARS = r"A-Za-z0-9_./-"
    PATH_TOKEN_CHARS = r"A-Za-z0-9_./-"

    DANGEROUS_COMMAND_TOKENS = {
        "rm", "dd", "mkfs", "kill", "chmod", "chown", "sudo",
        "shutdown", "reboot", "fdisk", "parted", "passwd", "userdel",
        "truncate", "shred",
    }
    DELETE_COMMAND_TOKENS = {"rm", "truncate", "shred"}

    FORBIDDEN_PATH_PATTERNS = (
        ("/", re.compile(r"(?<![A-Za-z0-9_./-])/(?![A-Za-z0-9_./-])")),
        ("/etc/passwd", re.compile(r"(?<![A-Za-z0-9_./-])/etc/passwd(?=$|[^A-Za-z0-9_./-])")),
        ("/etc/shadow", re.compile(r"(?<![A-Za-z0-9_./-])/etc/shadow(?=$|[^A-Za-z0-9_./-])")),
        ("/dev/sda", re.compile(r"(?<![A-Za-z0-9_./-])/dev/sda[0-9]*(?=$|[^A-Za-z0-9_./-])")),
        ("/dev/vda", re.compile(r"(?<![A-Za-z0-9_./-])/dev/vda[0-9]*(?=$|[^A-Za-z0-9_./-])")),
        ("/dev/nvme*", re.compile(r"(?<![A-Za-z0-9_./-])/dev/nvme[A-Za-z0-9_.-]*(?=$|[^A-Za-z0-9_./-])")),
    )
    SENSITIVE_PATH_PATTERNS = (
        ("/var/log", re.compile(r"(?<![A-Za-z0-9_./-])/var/log(?=$|/|[^A-Za-z0-9_./-])")),
        ("/etc", re.compile(r"(?<![A-Za-z0-9_./-])/etc(?=$|/|[^A-Za-z0-9_./-])")),
        ("/boot", re.compile(r"(?<![A-Za-z0-9_./-])/boot(?=$|/|[^A-Za-z0-9_./-])")),
        ("/proc", re.compile(r"(?<![A-Za-z0-9_./-])/proc(?=$|/|[^A-Za-z0-9_./-])")),
        ("/sys", re.compile(r"(?<![A-Za-z0-9_./-])/sys(?=$|/|[^A-Za-z0-9_./-])")),
        ("/dev", re.compile(r"(?<![A-Za-z0-9_./-])/dev(?=$|/|[^A-Za-z0-9_./-])")),
        ("/root", re.compile(r"(?<![A-Za-z0-9_./-])/root(?=$|/|[^A-Za-z0-9_./-])")),
        ("/home", re.compile(r"(?<![A-Za-z0-9_./-])/home(?=$|/|[^A-Za-z0-9_./-])")),
    )

    DESTRUCTIVE_TERMS = {
        "删除", "清空", "移除", "格式化", "覆盖", "修改", "写入", "重启",
        "关闭", "杀死", "停止", "销毁", "擦除",
        "delete", "remove", "clear", "format", "overwrite", "write",
        "modify", "kill", "shutdown", "reboot", "wipe", "destroy",
    }
    READONLY_TERMS = {
        "查看", "查询", "检查", "读取", "列出", "统计", "分析", "诊断",
        "搜索", "显示", "看看",
        "show", "check", "read", "list", "query", "inspect",
        "analyze", "diagnose", "search",
    }
    READONLY_TOOL_SAFE_PATHS = {"/var/log", "/home"}
    HARD_BLOCK_READ_PATHS = {"/etc/shadow"}
    PROTECTED_CREDENTIAL_PATTERNS = (
        ("/etc/gshadow", re.compile(r"(?<![A-Za-z0-9_./-])/etc/gshadow(?=$|[^A-Za-z0-9_./-])")),
        (".env", re.compile(
            r"(?<![A-Za-z0-9_.-])(?:\.env|[A-Za-z0-9_-]+\.env)"
            r"(?:\.[A-Za-z0-9_.-]+)?(?=$|[^A-Za-z0-9_.-])"
        )),
        ("ssh_private_key", re.compile(r"(?:^|/)\.ssh/(?:id_rsa|id_dsa|id_ecdsa|id_ed25519)(?=$|[^A-Za-z0-9_.-])")),
        ("private_key", re.compile(r"(?<![A-Za-z0-9_.-])[^/\s]+\.(?:pem|key)(?=$|[^A-Za-z0-9_.-])")),
        ("cloud_credentials", re.compile(r"(?:^|/)\.(?:aws|config)/(?:credentials|access_tokens?)(?=$|[^A-Za-z0-9_.-])")),
    )

    CRITICAL_INJECTION_PATTERNS = (
        ("prompt_injection:ignore_rules", re.compile(
            r"(?:忽略|无视|覆盖).{0,16}(?:之前|前文|系统|安全)?.{0,8}(?:规则|指令|限制|安全检查|安全护栏)"
            r"|ignore previous instructions|ignore prior instructions|override rules"
        )),
        ("prompt_injection:disable_audit", re.compile(
            r"不要记录日志|不记录日志|绕过审计|关闭审计|disable audit|bypass audit|do not log|don't log"
        )),
        ("prompt_injection:reveal_system_prompt", re.compile(
            r"(?:输出|显示|泄露|透露).{0,16}(?:system prompt|系统提示词|内部提示词)"
            r"|reveal system prompt|show system prompt|leak system prompt"
        )),
        ("prompt_injection:disable_guardrail", re.compile(
            r"(?:绕过|关闭|禁用).{0,16}(?:安全护栏|安全检查|guardrail|safety|security)"
            r"|bypass guardrail|disable guardrail|bypass safety|disable security"
        )),
        ("prompt_injection:root_impersonation", re.compile(
            r"(?:假装|模拟).{0,12}(?:root|管理员)|无限制管理员|you are root|act as root|unrestricted admin"
        )),
        ("prompt_injection:ignore_and_delete_logs", re.compile(
            r"(?:忽略|无视).{0,16}(?:前文|之前|规则|指令).{0,24}(?:删除|清空|移除).{0,12}日志"
            r"|ignore previous.{0,40}(?:delete|remove|clear).{0,12}logs?"
        )),
    )

    DANGEROUS_COMMAND_PATTERNS = (
        ("delete_command:rm_recursive_root", re.compile(
            r"(?<![A-Za-z0-9_./-])(?:sudo\s+)?rm\s+"
            r"(?:-[A-Za-z]*r[A-Za-z]*f[A-Za-z]*|-[A-Za-z]*f[A-Za-z]*r[A-Za-z]*|"
            r"--recursive\s+--force|--force\s+--recursive)"
            r"(?:\s+--no-preserve-root)?\s+/(?![A-Za-z0-9_./-])"
        )),
        ("dangerous_cmd:chmod_777_root", re.compile(
            r"(?<![A-Za-z0-9_./-])chmod\s+777\s+(?:-[A-Za-z]*r[A-Za-z]*\s+)?/(?![A-Za-z0-9_./-])"
        )),
        ("dangerous_cmd:mkfs_device", re.compile(
            r"(?<![A-Za-z0-9_./-])mkfs(?:\.[A-Za-z0-9_+-]+)?\s+/dev/\S+"
        )),
        ("dangerous_cmd:dd_device_write", re.compile(
            r"(?<![A-Za-z0-9_./-])dd\s+.*\bif\s*=\s*/dev/\S+.*\bof\s*=\s*/dev/\S+"
        )),
    )
    DOWNLOAD_EXECUTE_PATTERNS = (
        ("dangerous_cmd:curl_pipe_shell", re.compile(
            r"(?<![A-Za-z0-9_./-])curl(?![A-Za-z0-9_./-])[^\n\r|]*\|\s*(?:sh|bash)(?![A-Za-z0-9_./-])"
        )),
        ("dangerous_cmd:wget_pipe_shell", re.compile(
            r"(?<![A-Za-z0-9_./-])wget(?![A-Za-z0-9_./-])[^\n\r|]*"
            r"(?:-o\s*-|--output-document\s*=\s*-)?[^\n\r|]*\|\s*(?:sh|bash)(?![A-Za-z0-9_./-])"
        )),
    )

    def __init__(self):
        self.dangerous_cmds = config.DANGEROUS_COMMANDS
        self.dangerous_paths = config.DANGEROUS_PATHS
        self.dangerous_params = config.DANGEROUS_PARAMS
        self.injection_templates = config.INJECTION_TEMPLATES
        self.delete_commands = config.DELETE_COMMANDS
        self.risk_scorer = RiskScorer()

    # Layer 1: User input keyword detection
    def check_input(self, text: str) -> SecurityCheck:
        hits = []
        risk = 1
        normalized = self._normalize_text(text)

        # Check injection templates
        critical_injection_hits = self._match_critical_injection(normalized)
        if critical_injection_hits:
            hits.extend(critical_injection_hits)
            risk = max(risk, 5)

        for tmpl in self.injection_templates:
            if self._normalize_text(tmpl) in normalized:
                hits.append(f"injection_template:{tmpl}")
                risk = max(risk, 4)

        command_hits = self._match_dangerous_commands(normalized)
        if command_hits:
            hits.extend(command_hits)
            risk = max(risk, 5)

        path_risk, path_hits = self._assess_paths(normalized, mode="input")
        hits.extend(path_hits)
        risk = max(risk, path_risk)

        return SecurityCheck(
            passed=risk < 5,
            risk_level=risk,
            rule_hits=hits,
            channel="user_input",
        )

    # Layer 2: Tool output injection detection
    def check_tool_output(self, output: str) -> SecurityCheck:
        hits = []
        risk = 1
        normalized = self._normalize_text(output)
        critical_injection_hits = self._match_critical_injection(normalized)
        if critical_injection_hits:
            hits.extend(f"output_{hit}" for hit in critical_injection_hits)
            risk = max(risk, 4)
        for tmpl in self.injection_templates:
            if self._normalize_text(tmpl) in normalized:
                hits.append(f"output_injection:{tmpl}")
                risk = max(risk, 3)
        # Detect hidden commands in output
        if self._has_delete_command(normalized):
            hits.append("output_contains_delete_cmd")
            risk = max(risk, 4)
        return SecurityCheck(
            passed=risk < 4,
            risk_level=risk,
            rule_hits=hits,
            channel="tool_output",
        )

    # Layer 3: Tool selection validation
    def validate_tool_selection(self, tool_name: str, available_tools: List[str]) -> SecurityCheck:
        if tool_name not in available_tools:
            return SecurityCheck(
                passed=False,
                risk_level=4,
                rule_hits=[f"tool_not_in_whitelist:{tool_name}"],
                details=f"Available: {available_tools}",
            )
        return SecurityCheck(passed=True, risk_level=1, rule_hits=[])

    # Layer 4+5: Parameter and path validation
    def validate_tool_args(self, tool_name: str, args: dict) -> SecurityCheck:
        hits = []
        risk = 1
        for key, val in args.items():
            if isinstance(val, str):
                normalized = self._normalize_text(val)
                # Shell injection chars
                if any(c in val for c in [";", "|", "&", "$", "`", ">", "<", "\n", "\r"]):
                    hits.append(f"shell_injection_char:{key}")
                    risk = max(risk, 5)
                if "../" in normalized or "..\\" in normalized:
                    hits.append(f"path_traversal:{key}")
                    risk = max(risk, 5)
                command_hits = self._match_dangerous_commands(normalized)
                for hit in command_hits:
                    hits.append(f"{hit}_in_arg:{key}")
                    risk = max(risk, 5)
                path_risk, path_hits = self._assess_arg_paths(tool_name, key, normalized, val)
                hits.extend(path_hits)
                risk = max(risk, path_risk)
        return SecurityCheck(passed=risk < 5, risk_level=risk, rule_hits=hits)

    # Layer 6: Risk scoring
    def score(self, input_check: SecurityCheck, tool_check: SecurityCheck,
              arg_check: SecurityCheck) -> int:
        return max(input_check.risk_level, tool_check.risk_level, arg_check.risk_level)

    def score_100(
        self,
        input_check: Optional[SecurityCheck] = None,
        tool_check: Optional[SecurityCheck] = None,
        arg_check: Optional[SecurityCheck] = None,
        output_check: Optional[SecurityCheck] = None,
        tool_name: str = "",
        arguments: Optional[dict] = None,
        extra_factors: Optional[List[str]] = None,
    ) -> RiskScoreResult:
        return self.risk_scorer.score(
            input_check=input_check,
            tool_check=tool_check,
            arg_check=arg_check,
            output_check=output_check,
            tool_name=tool_name,
            arguments=arguments or {},
            extra_factors=extra_factors or [],
        )

    # Layer 7+10: Alternative suggestions
    def suggest_alternative(self, risk_level: int, user_input: str) -> Optional[str]:
        normalized = self._normalize_text(user_input)
        if risk_level >= 5 and self._has_delete_command(normalized):
            return (
                "检测到删除类操作请求。出于安全原则，系统不自动执行删除。"
                "建议：1) 先备份目标文件；2) 使用 logrotate 进行日志轮转；"
                "3) 用 gzip 压缩旧日志；4) 人工确认后再处置。"
            )
        if "chmod 777" in user_input:
            return "建议改用 `chmod 640`（文件）或 `chmod 750`（目录），遵循最小权限原则。"
        if risk_level >= 4:
            return "该操作涉及系统安全边界，建议人工确认后再执行。"
        return None

    def _normalize_text(self, text: str) -> str:
        normalized = str(text or "")
        for _ in range(2):
            decoded = unquote(normalized)
            if decoded == normalized:
                break
            normalized = decoded
        normalized = unicodedata.normalize("NFKC", normalized)
        normalized = "".join(
            char for char in normalized if unicodedata.category(char) != "Cf"
        ).lower()
        return re.sub(r"\s+", " ", normalized).strip()

    def _token_pattern(self, token: str) -> re.Pattern:
        return re.compile(
            rf"(?<![{self.COMMAND_TOKEN_CHARS}]){re.escape(token)}(?![{self.COMMAND_TOKEN_CHARS}])"
        )

    def _has_command_token(self, text: str, token: str) -> bool:
        return bool(self._token_pattern(token).search(text))

    def _has_any_term(self, text: str, terms: set[str]) -> bool:
        for term in terms:
            normalized = self._normalize_text(term)
            if re.fullmatch(r"[a-z0-9_-]+", normalized):
                if self._has_command_token(text, normalized):
                    return True
            elif normalized in text:
                return True
        return False

    def _match_dangerous_commands(self, text: str) -> List[str]:
        hits = []
        for rule, pattern in self.DANGEROUS_COMMAND_PATTERNS + self.DOWNLOAD_EXECUTE_PATTERNS:
            if pattern.search(text):
                hits.append(rule)
        for cmd in sorted(self.DANGEROUS_COMMAND_TOKENS):
            if self._has_command_token(text, cmd):
                hits.append(f"dangerous_cmd:{cmd}")
        return self._dedupe(hits)

    def _match_critical_injection(self, text: str) -> List[str]:
        return [rule for rule, pattern in self.CRITICAL_INJECTION_PATTERNS if pattern.search(text)]

    def _has_delete_command(self, text: str) -> bool:
        if any(pattern.search(text) for _, pattern in self.DANGEROUS_COMMAND_PATTERNS):
            return True
        return any(self._has_command_token(text, cmd) for cmd in self.DELETE_COMMAND_TOKENS)

    def _match_paths(self, text: str, patterns) -> List[str]:
        return [path for path, pattern in patterns if pattern.search(text)]

    def _assess_paths(self, text: str, mode: str) -> tuple[int, List[str]]:
        hits = []
        risk = 1
        forbidden_paths = self._match_paths(text, self.FORBIDDEN_PATH_PATTERNS)
        sensitive_paths = self._match_paths(text, self.SENSITIVE_PATH_PATTERNS)
        credential_paths = self._match_paths(text, self.PROTECTED_CREDENTIAL_PATTERNS)
        destructive = self._has_any_term(text, self.DESTRUCTIVE_TERMS) or self._has_delete_command(text)
        readonly = self._has_any_term(text, self.READONLY_TERMS)

        if credential_paths:
            hits.extend(f"protected_credential_read:{path}" for path in credential_paths)
            risk = max(risk, 5)

        if forbidden_paths:
            if destructive:
                hits.extend(f"destructive_forbidden_path:{path}" for path in forbidden_paths)
                risk = max(risk, 5)
            elif readonly:
                for path in forbidden_paths:
                    if path in self.HARD_BLOCK_READ_PATHS:
                        hits.append(f"protected_secret_read:{path}")
                        risk = max(risk, 5)
                    else:
                        hits.append(f"readonly_forbidden_path:{path}")
                        risk = max(risk, 3)
            else:
                hits.extend(f"forbidden_path:{path}" for path in forbidden_paths)
                risk = max(risk, 4)

        if sensitive_paths:
            if destructive:
                hits.extend(f"destructive_path_operation:{path}" for path in sensitive_paths)
                risk = max(risk, 5)
            elif readonly:
                hits.extend(f"readonly_path_query:{path}" for path in sensitive_paths)
                risk = max(risk, 1)
            else:
                hits.extend(f"sensitive_path:{path}" for path in sensitive_paths)
                risk = max(risk, 3 if mode == "input" else 4)

        return risk, self._dedupe(hits)

    def _assess_arg_paths(self, tool_name: str, key: str, text: str, original_value: str) -> tuple[int, List[str]]:
        hits = []
        risk = 1
        forbidden_paths = self._match_paths(text, self.FORBIDDEN_PATH_PATTERNS)
        sensitive_paths = self._match_paths(text, self.SENSITIVE_PATH_PATTERNS)
        credential_paths = self._match_paths(text, self.PROTECTED_CREDENTIAL_PATTERNS)
        destructive = self._has_any_term(text, self.DESTRUCTIVE_TERMS) or self._has_delete_command(text)

        if credential_paths:
            hits.extend(
                f"protected_credential_in_arg:{key}={self._summarize_arg(original_value)}"
                for _ in credential_paths
            )
            risk = max(risk, 5)

        if forbidden_paths:
            hits.extend(f"forbidden_path_in_arg:{key}={self._summarize_arg(original_value)}" for _ in forbidden_paths)
            risk = max(risk, 5)

        for path in sensitive_paths:
            if destructive:
                hits.append(f"destructive_path_in_arg:{key}={self._summarize_arg(original_value)}")
                risk = max(risk, 5)
            elif tool_name in self._readonly_tools() and path in self.READONLY_TOOL_SAFE_PATHS:
                hits.append(f"readonly_path_in_arg:{key}={path}")
                risk = max(risk, 1)
            else:
                hits.append(f"dangerous_path_in_arg:{key}={self._summarize_arg(original_value)}")
                risk = max(risk, 4)

        return risk, self._dedupe(hits)

    def _readonly_tools(self) -> set[str]:
        return {
            "disk_usage",
            "process_list",
            "network_status",
            "journal_query",
            "large_file_scan",
            "get_port_usage",
            "get_memory_status",
            "get_service_status",
            "get_cpu_status",
            "config_drift_check",
            "zombie_process_check",
            "disk_io_analysis",
            "impact_analysis",
            "safe_cleanup_scan",
            "safe_cleanup_plan",
        }

    def _summarize_arg(self, value: str) -> str:
        text = str(value)
        return text if len(text) <= 120 else text[:117] + "..."

    def _dedupe(self, values: List[str]) -> List[str]:
        return list(dict.fromkeys(values))
