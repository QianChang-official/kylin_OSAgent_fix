"""Tool: large_file_scan - scan large files without shell execution."""
import os
import re
from datetime import datetime
from pathlib import Path

from backend import config

from .registry import ToolResult, ToolSchema, get_registry

SIZE_RE = re.compile(r"^\+([1-9][0-9]*)([KMG]?)$", re.IGNORECASE)


def _large_file_scan(path: str = "/var/log", size: str = "+100M") -> ToolResult:
    warnings: list[str] = []
    audit = {
        "actual_command": ["python", "os.walk", str(path), str(size)],
        "executor_user": "",
        "execution_success": False,
        "stdout_summary": "",
        "stderr_summary": "",
    }
    threshold = _parse_size(size)
    if threshold is None:
        return ToolResult(
            tool="large_file_scan",
            status="command_failed",
            error="Invalid size threshold. Use format like +100M, +1G, or +512K.",
        )

    valid_path, path_error = _validate_scan_path(path)
    if path_error:
        return ToolResult(tool="large_file_scan", status="command_failed", error=path_error)
    if valid_path is None:
        return ToolResult(tool="large_file_scan", status="command_failed", error="Invalid scan path")
    if not valid_path.exists():
        return ToolResult(tool="large_file_scan", status="command_failed", error=f"Path not found: {valid_path}")
    if not valid_path.is_dir():
        return ToolResult(tool="large_file_scan", status="command_failed", error=f"Path is not a directory: {valid_path}")

    files_scanned = 0
    max_files_reached = False
    matches: list[dict] = []

    def on_walk_error(error: OSError):
        _add_warning(warnings, f"Skipped {getattr(error, 'filename', 'unknown')}: {error.strerror}")

    for root, dirs, files in os.walk(valid_path, topdown=True, onerror=on_walk_error, followlinks=False):
        root_path = Path(root)
        dirs[:] = _safe_child_dirs(root_path, dirs, warnings)

        for filename in files:
            if files_scanned >= config.LARGE_FILE_SCAN_MAX_FILES:
                max_files_reached = True
                break

            file_path = root_path / filename
            try:
                if file_path.is_symlink():
                    _add_warning(warnings, f"Skipped symlink file: {file_path}")
                    continue
                if not file_path.is_file():
                    continue
                file_stat = file_path.stat()
                file_size = file_stat.st_size
            except PermissionError:
                _add_warning(warnings, f"Permission denied: {file_path}")
                continue
            except OSError as exc:
                _add_warning(warnings, f"Skipped {file_path}: {exc}")
                continue

            files_scanned += 1
            if file_size >= threshold:
                matches.append({
                    "size": _human_size(file_size),
                    "bytes": file_size,
                    "path": str(file_path),
                    "modified_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    "safety_tip": "Confirm ownership and backup policy before any cleanup action.",
                })

        if max_files_reached:
            _add_warning(warnings, f"Reached max scan file limit: {config.LARGE_FILE_SCAN_MAX_FILES}")
            break

    matches.sort(key=lambda item: item["bytes"], reverse=True)
    limited_matches = matches[: config.LARGE_FILE_SCAN_MAX_RESULTS]
    if len(matches) > len(limited_matches):
        _add_warning(warnings, f"Returned top {config.LARGE_FILE_SCAN_MAX_RESULTS} results only")

    data = {
        "files": limited_matches,
        "warnings": warnings,
        "scanned_files": files_scanned,
        "max_files_reached": max_files_reached,
    }
    audit["execution_success"] = True
    audit["stdout_summary"] = f"scanned_files={files_scanned}, results={len(limited_matches)}"
    raw_output = "\n".join(f"{item['size']}\t{item['path']}" for item in limited_matches)
    if warnings:
        raw_output = "\n".join([raw_output, "WARNINGS:", *warnings]).strip()
    if not limited_matches and not warnings:
        return ToolResult(tool="large_file_scan", status="no_output", data=data, audit=audit)
    return ToolResult(tool="large_file_scan", status="success", data=data, raw_output=raw_output, audit=audit)


def _parse_size(value: str) -> int | None:
    if not isinstance(value, str):
        return None
    match = SIZE_RE.match(value.strip())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).upper()
    multiplier = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}[unit]
    return amount * multiplier


def _validate_scan_path(path: str) -> tuple[Path | None, str]:
    if not isinstance(path, str) or not path.strip():
        return None, "Scan path must be a non-empty string"
    if any(marker in path for marker in config.COMMAND_SHELL_META_CHARS):
        return None, "Scan path contains blocked shell characters"

    candidate = Path(path).expanduser().resolve(strict=False)
    blocked_roots = [Path(root).resolve(strict=False) for root in config.LARGE_FILE_SCAN_BLOCKED_ROOTS]
    allowed_roots = [Path(root).resolve(strict=False) for root in config.LARGE_FILE_SCAN_ALLOWED_ROOTS]

    for blocked in blocked_roots:
        if _is_root_path(blocked):
            if candidate == blocked:
                return None, f"Scanning sensitive path is blocked: {candidate}"
            continue
        if _path_is_within(candidate, blocked):
            return None, f"Scanning sensitive path is blocked: {candidate}"

    if not any(_path_is_within(candidate, allowed) for allowed in allowed_roots):
        allowed_text = ", ".join(str(root) for root in allowed_roots)
        return None, f"Scan path is outside allowed roots: {allowed_text}"

    return candidate, ""


def _safe_child_dirs(root_path: Path, dirs: list[str], warnings: list[str]) -> list[str]:
    safe_dirs = []
    blocked_roots = [Path(root).resolve(strict=False) for root in config.LARGE_FILE_SCAN_BLOCKED_ROOTS]
    for dirname in dirs:
        child = root_path / dirname
        try:
            if child.is_symlink():
                _add_warning(warnings, f"Skipped symlink directory: {child}")
                continue
            resolved = child.resolve(strict=False)
            if any(not _is_root_path(blocked) and _path_is_within(resolved, blocked) for blocked in blocked_roots):
                _add_warning(warnings, f"Skipped sensitive directory: {child}")
                continue
        except OSError as exc:
            _add_warning(warnings, f"Skipped directory {child}: {exc}")
            continue
        safe_dirs.append(dirname)
    return safe_dirs


def _path_is_within(candidate: Path, root: Path) -> bool:
    return candidate == root or candidate.is_relative_to(root)


def _is_root_path(path: Path) -> bool:
    return path.parent == path


def _add_warning(warnings: list[str], message: str):
    if len(warnings) < config.LARGE_FILE_SCAN_MAX_RESULTS:
        warnings.append(message)


def _human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "K", "M", "G", "T"]:
        if value < 1024 or unit == "T":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{num_bytes}B"


SCHEMA = ToolSchema(
    name="large_file_scan",
    description="Scan for large files in an allowed directory (default /var/log, +100M)",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Allowed directory to scan"},
            "size": {"type": "string", "description": "Size threshold, e.g. +100M"},
        },
        "required": [],
    },
)


def register():
    get_registry().register(SCHEMA, lambda path="/var/log", size="+100M": _large_file_scan(path, size))
