"""Command execution result structures for SafeOpsAgent."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommandResult:
    success: bool
    returncode: Optional[int]
    stdout: str
    stderr: str
    command: list[str] = field(default_factory=list)
    duration_ms: int = 0
    executor_user: str = ""
    error: str = ""

