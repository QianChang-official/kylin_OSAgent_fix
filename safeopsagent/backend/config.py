"""SafeOpsAgent configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(
        item.strip().rstrip("/")
        for item in os.environ.get(name, default).split(",")
        if item.strip()
    )

# LLM
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "").strip().lower()
MODEL_API_BASE = os.environ.get("MODEL_API_BASE", "").strip().rstrip("/")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "").strip()

# Legacy generic provider configuration. Kept for backward compatibility.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "offline_safe").lower()
LLM_API_BASE = os.environ.get("LLM_API_BASE", "").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", "15"))
LLM_MAX_OUTPUT_CHARS = int(os.environ.get("LLM_MAX_OUTPUT_CHARS", "4000"))

# Legacy/vendor-specific variables. Model names stay explicit; no provider model
# version is selected by application code.
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "")
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")

# Agent
MAX_CONTEXT_ROUNDS = 6
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "1800"))
SESSION_MAX_MESSAGES = int(os.environ.get("SESSION_MAX_MESSAGES", "20"))
CONFIRMATION_TTL_SECONDS = int(os.environ.get("CONFIRMATION_TTL_SECONDS", "300"))
TOOL_RESULT_MAX_LINES = 50
REQUEST_TIMEOUT = 30
CPU_SAMPLE_INTERVAL_SECONDS = float(os.environ.get("CPU_SAMPLE_INTERVAL_SECONDS", "1.0"))

# Console authentication. Disabled by default for the localhost-only demo;
# deployments should enable it or place the service behind an authenticated
# reverse proxy. Passwords are stored only as PBKDF2 verifier strings.
CONSOLE_AUTH_ENABLED = _env_bool("CONSOLE_AUTH_ENABLED", False)
CONSOLE_AUTH_USERNAME = os.environ.get("CONSOLE_AUTH_USERNAME", "").strip()
CONSOLE_AUTH_PASSWORD_HASH = os.environ.get("CONSOLE_AUTH_PASSWORD_HASH", "").strip()
CONSOLE_AUTH_SESSION_SECRET = os.environ.get("CONSOLE_AUTH_SESSION_SECRET", "")
CONSOLE_AUTH_SESSION_TTL_SECONDS = int(
    os.environ.get("CONSOLE_AUTH_SESSION_TTL_SECONDS", "3600")
)
CONSOLE_AUTH_SECURE_COOKIE = _env_bool("CONSOLE_AUTH_SECURE_COOKIE", False)
CONSOLE_AUTH_COOKIE_NAME = "safeops_session"
CONSOLE_LOGIN_ATTEMPT_LIMIT = int(os.environ.get("CONSOLE_LOGIN_ATTEMPT_LIMIT", "5"))
CONSOLE_LOGIN_WINDOW_SECONDS = int(os.environ.get("CONSOLE_LOGIN_WINDOW_SECONDS", "60"))

# The Vue console is same-origin in production. Only explicit development
# origins receive cross-origin API access.
CORS_ALLOWED_ORIGINS = tuple(
    origin
    for origin in _env_list(
        "CORS_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    )
    if origin != "*"
)

# Completed Codex Security scans are imported read-only from this private,
# external directory. The production backend never launches the scanner.
CODEX_SECURITY_RESULTS_DIR = os.environ.get("CODEX_SECURITY_RESULTS_DIR", "").strip()

# Audit
AUDIT_DB_PATH = PROJECT_DIR / "data" / "audit.db"
AUDIT_RETENTION_DAYS = 7

# Security
DELETE_COMMANDS = {"rm", "rm -rf", "truncate", "shred"}
DANGEROUS_COMMANDS = {"rm", "mkfs", "dd", "chmod 777", "chown root", "userdel", "passwd", "kill -9", "shutdown", "reboot", "init", "fdisk", "parted", "wget", "curl"}
DANGEROUS_PATHS = {"/etc", "/boot", "/proc", "/sys", "/dev", "/root", "/", "/var/lib", "/usr/sbin", "/home"}
DANGEROUS_PARAMS = {"-rf", "--no-preserve-root", "/dev/sda", "chmod 777", "> /dev/sda", "--force", "-y", "--yes", "> /dev/null"}
INJECTION_TEMPLATES = [
    "忽略前文", "忽略之前的规则", "你现在是 root", "覆盖系统规则",
    "不要记录日志", "绕过安全检查", "关闭安全模块",
    "Ignore previous instructions", "Do not log", "Bypass safety",
    "ignore previous", "override rules", "disable security", "you are now root"
]

# Execution
COMMAND_WHITELIST = {
    "ss", "lsof", "netstat", "ps", "df", "free", "systemctl",
    "journalctl", "whoami", "id", "last", "find", "du",
}
COMMAND_DENYLIST = {
    "rm", "chmod", "chown", "mkfs", "dd", "reboot", "shutdown",
    "sudo", "kill", "bash", "sh", "curl", "wget",
}
COMMAND_SHELL_META_CHARS = {";", "|", "&", ">", "<", "`", "$", "\n", "\r", "\x00"}
EXEC_TIMEOUT = 10
EXEC_MAX_OUTPUT_LINES = 100
EXEC_MAX_OUTPUT_BYTES = 65536

LARGE_FILE_SCAN_ALLOWED_ROOTS = ("/var/log", "/home", "/tmp")
LARGE_FILE_SCAN_BLOCKED_ROOTS = ("/", "/etc", "/boot", "/dev", "/proc", "/sys", "/run")
LARGE_FILE_SCAN_MAX_FILES = 5000
LARGE_FILE_SCAN_MAX_RESULTS = 50

# Reversible cleanup. These roots are intentionally narrower than the
# read-only large-file scanner.
SAFE_CLEANUP_ALLOWED_ROOTS = tuple(
    item.strip()
    for item in os.environ.get("SAFE_CLEANUP_ALLOWED_ROOTS", "/tmp,/var/tmp").split(",")
    if item.strip()
)
SAFE_CLEANUP_PLAN_TTL_SECONDS = int(os.environ.get("SAFE_CLEANUP_PLAN_TTL_SECONDS", "900"))
SAFE_CLEANUP_MIN_AGE_HOURS = int(os.environ.get("SAFE_CLEANUP_MIN_AGE_HOURS", "24"))
SAFE_CLEANUP_MAX_SCAN_FILES = int(os.environ.get("SAFE_CLEANUP_MAX_SCAN_FILES", "5000"))
SAFE_CLEANUP_MAX_FILES = int(os.environ.get("SAFE_CLEANUP_MAX_FILES", "50"))
SAFE_CLEANUP_MAX_FILE_BYTES = int(
    os.environ.get("SAFE_CLEANUP_MAX_FILE_BYTES", str(100 * 1024 * 1024))
)
SAFE_CLEANUP_MAX_TOTAL_BYTES = int(
    os.environ.get("SAFE_CLEANUP_MAX_TOTAL_BYTES", str(500 * 1024 * 1024))
)
SAFE_CLEANUP_ALLOWED_SUFFIXES = (".tmp", ".temp", ".cache", ".old", ".bak", ".log")

# RCA fallback template
RCA_DISK_TEMPLATE = (
    "根据检测结果，`{path}` 占用 `{size}`。"
    "建议先查看日志归属服务，考虑日志轮转或备份，不建议直接删除。"
)
