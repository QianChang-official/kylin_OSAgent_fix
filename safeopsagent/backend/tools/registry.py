"""MCP-style Tool Registry — discoverable, schema-validated, auditable."""
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSchema:
    name: str
    description: str
    input_schema: dict  # JSON Schema


@dataclass
class ToolResult:
    tool: str
    status: str  # "success" | "command_failed" | "no_output" | "parse_warning" | "capability_missing"
    data: Any = None
    raw_output: str = ""
    error: str = ""
    audit: dict = field(default_factory=dict)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSchema] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, schema: ToolSchema, handler: Callable) -> None:
        self._tools[schema.name] = schema
        self._handlers[schema.name] = handler

    def list_tools(self) -> list:
        return [
            {"name": s.name, "description": s.description, "inputSchema": s.input_schema}
            for s in self._tools.values()
        ]

    def get_schema(self, name: str) -> ToolSchema | None:
        return self._tools.get(name)

    def validate_args(self, name: str, args: dict) -> tuple:
        schema = self._tools.get(name)
        if schema is None:
            return False, f"Tool '{name}' not found"
        return self._validate_args(schema, args)

    def call(self, name: str, args: dict) -> ToolResult:
        if name not in self._handlers:
            return ToolResult(tool=name, status="capability_missing", error=f"Tool '{name}' not found")
        schema = self._tools[name]
        # Basic parameter validation
        valid, err = self._validate_args(schema, args)
        if not valid:
            return ToolResult(tool=name, status="command_failed", error=err)
        try:
            return self._handlers[name](**args)
        except Exception as e:
            return ToolResult(tool=name, status="command_failed", error=str(e))

    def _validate_args(self, schema: ToolSchema, args: dict) -> tuple:
        required = schema.input_schema.get("required", [])
        props = schema.input_schema.get("properties", {})
        for key in required:
            if key not in args:
                return False, f"Missing required argument: {key}"
        for key, val in args.items():
            if key not in props:
                return False, f"Unknown argument: {key}"
            prop_type = props[key].get("type")
            if prop_type == "string" and not isinstance(val, str):
                return False, f"Argument {key} must be string"
            if prop_type == "integer" and (isinstance(val, bool) or not isinstance(val, int)):
                return False, f"Argument {key} must be integer"
            valid, err = self._validate_constraints(key, val, props[key])
            if not valid:
                return False, err
        return True, ""

    def _validate_constraints(self, key: str, val: Any, prop: dict) -> tuple:
        if isinstance(val, int) and not isinstance(val, bool):
            minimum = prop.get("minimum")
            maximum = prop.get("maximum")
            if minimum is not None and val < minimum:
                return False, f"Argument {key} must be >= {minimum}"
            if maximum is not None and val > maximum:
                return False, f"Argument {key} must be <= {maximum}"
        if isinstance(val, str):
            min_length = prop.get("minLength")
            max_length = prop.get("maxLength")
            pattern = prop.get("pattern")
            if min_length is not None and len(val) < min_length:
                return False, f"Argument {key} length must be >= {min_length}"
            if max_length is not None and len(val) > max_length:
                return False, f"Argument {key} length must be <= {max_length}"
            if pattern and not re.fullmatch(pattern, val):
                return False, f"Argument {key} does not match required pattern"
        return True, ""


# Singleton registry
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _registry


def command_audit(result) -> dict:
    return {
        "actual_command": result.command,
        "executor_user": result.executor_user,
        "execution_success": result.success,
        "stdout_summary": _summary(result.stdout),
        "stderr_summary": _summary(result.stderr),
        "duration_ms": result.duration_ms,
        "returncode": result.returncode,
        "error": result.error,
    }


def _summary(text: str, limit: int = 500) -> str:
    if not text:
        return ""
    clean = str(text)
    return clean[:limit] + ("...[truncated]" if len(clean) > limit else "")
