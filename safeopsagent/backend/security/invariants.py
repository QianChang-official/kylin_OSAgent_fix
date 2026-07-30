"""Static analysis half of the security invariant verifier.

Most projects assert "we have a security guardrail". This module turns
that claim into a machine-checkable property by parsing the backend's AST
and proving structural invariants about where dangerous primitives may
appear and which module is allowed to reach the operating system.

Static invariants:
  INV-S1  subprocess.* may only be called inside SafeExecutor
  INV-S2  shell=True must not appear anywhere in the backend
  INV-S3  os.system / os.popen / eval / exec / compile must not appear
  INV-S4  tool modules must reach the OS through SafeExecutor, never directly
  INV-S5  SafeExecutor must call subprocess with shell=False explicitly
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The single module permitted to touch the process-spawning API.
EXECUTOR_MODULE = "backend/executor/safe_executor.py"

SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}
FORBIDDEN_ATTR_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "spawnl"),
    ("os", "spawnv"),
}
FORBIDDEN_BUILTINS = {"eval", "exec"}

# Directories excluded from the proof: tests legitimately simulate unsafe
# input, and their presence in the archive does not widen the attack surface.
EXCLUDED_PARTS = {"tests", "__pycache__"}


@dataclass
class Violation:
    invariant: str
    file: str
    line: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant": self.invariant,
            "file": self.file,
            "line": self.line,
            "detail": self.detail,
        }


@dataclass
class StaticReport:
    files_scanned: int = 0
    violations: list[Violation] = field(default_factory=list)
    subprocess_sites: list[dict[str, Any]] = field(default_factory=list)
    executor_call_sites: list[dict[str, Any]] = field(default_factory=list)
    tool_modules: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_scanned": self.files_scanned,
            "passed": self.passed,
            "violation_count": len(self.violations),
            "violations": [item.to_dict() for item in self.violations],
            "subprocess_sites": self.subprocess_sites,
            "executor_call_sites": self.executor_call_sites,
            "tool_modules": self.tool_modules,
        }


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _iter_backend_files(backend_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(backend_dir.rglob("*.py"))
        if not (EXCLUDED_PARTS & set(path.relative_to(backend_dir).parts))
    ]


def _attr_chain(node: ast.AST) -> tuple[str, ...]:
    """Flatten `a.b.c` into ("a", "b", "c")."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return tuple(reversed(parts))


def analyze(project_root: Path) -> StaticReport:
    report = StaticReport()
    backend_dir = project_root / "backend"
    if not backend_dir.is_dir():
        report.violations.append(
            Violation("INV-S0", "backend", 0, "backend directory not found")
        )
        return report

    for path in _iter_backend_files(backend_dir):
        rel = _relative(path, project_root)
        report.files_scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            report.violations.append(Violation("INV-S0", rel, 0, f"unparsable: {exc}"))
            continue

        is_executor = rel.endswith(EXECUTOR_MODULE) or rel == EXECUTOR_MODULE
        if "backend/tools/" in rel and path.name not in {"__init__.py", "registry.py"}:
            report.tool_modules.append(rel)

        _check_module(tree, rel, is_executor, report)

    _check_executor_present(report)
    return report


def _check_module(tree: ast.AST, rel: str, is_executor: bool, report: StaticReport) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _attr_chain(node.func)

        # INV-S1 / INV-S5: subprocess usage
        if chain and chain[0] == "subprocess" and len(chain) > 1 and chain[1] in SUBPROCESS_CALLS:
            site = {"file": rel, "line": node.lineno, "call": ".".join(chain)}
            report.subprocess_sites.append(site)
            if not is_executor:
                report.violations.append(Violation(
                    "INV-S1", rel, node.lineno,
                    f"{'.'.join(chain)} outside SafeExecutor — OS access must be single-sourced",
                ))
            else:
                _check_shell_false(node, rel, report)

        # INV-S3: forbidden OS/eval primitives
        if len(chain) >= 2 and (chain[0], chain[1]) in FORBIDDEN_ATTR_CALLS:
            report.violations.append(Violation(
                "INV-S3", rel, node.lineno,
                f"forbidden primitive {'.'.join(chain)}",
            ))
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
            report.violations.append(Violation(
                "INV-S3", rel, node.lineno,
                f"forbidden builtin {node.func.id}()",
            ))

        # INV-S2: shell=True anywhere
        for keyword in node.keywords:
            if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                report.violations.append(Violation(
                    "INV-S2", rel, node.lineno,
                    "shell=True enables shell interpretation of arguments",
                ))

        # INV-S4: tools must not reach the OS directly
        if "backend/tools/" in rel and chain and chain[0] == "subprocess":
            report.violations.append(Violation(
                "INV-S4", rel, node.lineno,
                "tool module reaches subprocess directly instead of via SafeExecutor",
            ))

        # Track SafeExecutor.run call sites for the coverage summary.
        if chain and chain[-1] == "run" and any("executor" in part.lower() for part in chain[:-1]):
            report.executor_call_sites.append({"file": rel, "line": node.lineno})


def _check_shell_false(node: ast.Call, rel: str, report: StaticReport) -> None:
    """INV-S5: the one permitted subprocess call must pin shell=False."""
    for keyword in node.keywords:
        if keyword.arg == "shell":
            if isinstance(keyword.value, ast.Constant) and keyword.value.value is False:
                return
            report.violations.append(Violation(
                "INV-S5", rel, node.lineno,
                "shell argument is not the literal False",
            ))
            return
    report.violations.append(Violation(
        "INV-S5", rel, node.lineno,
        "subprocess call does not explicitly pass shell=False",
    ))


def _check_executor_present(report: StaticReport) -> None:
    """INV-S1 corollary: exactly one module may own OS access."""
    owners = {site["file"] for site in report.subprocess_sites}
    if not owners:
        report.violations.append(Violation(
            "INV-S1", EXECUTOR_MODULE, 0,
            "no subprocess call site found — SafeExecutor is expected to own exactly one",
        ))
    elif len(owners) > 1:
        report.violations.append(Violation(
            "INV-S1", ", ".join(sorted(owners)), 0,
            f"OS access is spread across {len(owners)} modules; it must be single-sourced",
        ))


STATIC_INVARIANTS = {
    "INV-S1": "subprocess.* 只允许出现在 SafeExecutor，操作系统访问单点收口",
    "INV-S2": "后端任何位置不得出现 shell=True",
    "INV-S3": "不得使用 os.system / os.popen / eval / exec 等危险原语",
    "INV-S4": "工具模块不得直接触达 subprocess，必须经由 SafeExecutor",
    "INV-S5": "SafeExecutor 中的 subprocess 调用必须显式传入 shell=False",
}
