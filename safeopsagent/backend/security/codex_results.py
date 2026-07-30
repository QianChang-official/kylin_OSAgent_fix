"""Read-only importer for sealed Codex Security scan artifacts.

Codex Security runs on a separate supported scan host. SafeOpsAgent never
launches it from the operations API; it only reads completed, hash-verified
JSON artifacts from a configured private directory outside this repository.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCAN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_FINDINGS_RETURNED = 200
MAX_JSON_DEPTH = 24
MAX_JSON_CONTAINER_ITEMS = 10_000
MAX_JSON_NODES = 50_000
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "informational", "unknown"}
ALLOWED_COMPLETENESS = {"complete", "partial", "unknown"}
_UNSAFE_FORMAT_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
    "\ufeff",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


class CodexResultError(ValueError):
    """A scan directory or artifact failed containment/integrity validation."""


@dataclass(frozen=True)
class _CheckedDocument:
    payload: dict[str, Any]
    digest: str


class CodexResultStore:
    def __init__(self, root: Path, project_root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.project_root = Path(project_root).resolve()
        if _is_contained(self.project_root, self.root):
            raise CodexResultError("Codex Security result root must be outside the project")

    def list_scans(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.root.is_dir() or self.root.is_symlink():
            return []
        summaries: list[dict[str, Any]] = []
        try:
            candidates = sorted(
                self.root.iterdir(),
                key=_mtime_or_zero,
                reverse=True,
            )
        except OSError:
            return []
        for candidate in candidates:
            if len(summaries) >= max(1, min(int(limit), 100)):
                break
            if not SCAN_ID_PATTERN.fullmatch(candidate.name):
                continue
            try:
                loaded = self.load(candidate.name, finding_limit=0)
            except CodexResultError:
                continue
            summaries.append(
                {
                    "scan_id": loaded["scan_id"],
                    "directory_id": candidate.name,
                    "completed_at": loaded["completed_at"],
                    "target": loaded["target"],
                    "coverage": loaded["coverage"],
                    "finding_count": loaded["finding_count"],
                    "severity_counts": loaded["severity_counts"],
                    "integrity_verified": True,
                }
            )
        return summaries

    def load(self, scan_id: str, finding_limit: int = 100) -> dict[str, Any]:
        if not SCAN_ID_PATTERN.fullmatch(str(scan_id)):
            raise CodexResultError("Invalid scan directory identifier")
        candidate = self.root / scan_id
        if candidate.is_symlink():
            raise CodexResultError("Scan directory must not be a symbolic link")
        scan_dir = candidate.resolve()
        if scan_dir.parent != self.root or not scan_dir.is_dir():
            raise CodexResultError("Scan directory was not found or is not a regular directory")

        manifest_doc = _read_document(scan_dir, "scan-manifest.json")
        manifest = manifest_doc.payload
        _require_document_type(manifest, "codex-security.scan-manifest")
        scan = manifest.get("scan")
        if not isinstance(scan, dict) or scan.get("status") != "completed":
            raise CodexResultError("Codex Security scan is not completed")

        findings_ref = _safe_reference(scan.get("findingsRef"), "findings.json")
        coverage_ref = _safe_reference(scan.get("coverageRef"), "coverage.json")
        findings_doc = _read_document(scan_dir, findings_ref)
        coverage_doc = _read_document(scan_dir, coverage_ref)
        _verify_artifact_digest(scan, findings_ref, findings_doc.digest)
        _verify_artifact_digest(scan, coverage_ref, coverage_doc.digest)
        _require_document_type(findings_doc.payload, "codex-security.findings")
        _require_document_type(coverage_doc.payload, "codex-security.coverage")

        actual_scan_id = _clean_text(scan.get("id"), 100)
        if not actual_scan_id:
            raise CodexResultError("Scan manifest is missing its scan id")
        if findings_doc.payload.get("scanId") != scan.get("id"):
            raise CodexResultError("Findings scan id does not match the manifest")
        if coverage_doc.payload.get("scanId") != scan.get("id"):
            raise CodexResultError("Coverage scan id does not match the manifest")

        raw_findings = findings_doc.payload.get("findings")
        if not isinstance(raw_findings, list):
            raise CodexResultError("Findings document does not contain a findings array")
        normalized = [_normalize_finding(item) for item in raw_findings if isinstance(item, dict)]
        severity_counts = {level: 0 for level in ["critical", "high", "medium", "low", "informational", "unknown"]}
        for item in normalized:
            severity_counts[item["severity"]] += 1

        coverage_value = str(coverage_doc.payload.get("completeness", "unknown")).lower()
        if coverage_value not in ALLOWED_COMPLETENESS:
            coverage_value = "unknown"
        target = scan.get("target") if isinstance(scan.get("target"), dict) else {}
        producer = scan.get("producer") if isinstance(scan.get("producer"), dict) else {}
        requested_limit = max(0, min(int(finding_limit), MAX_FINDINGS_RETURNED))
        return {
            "scan_id": actual_scan_id,
            "directory_id": scan_id,
            "completed_at": _clean_text(scan.get("completedAt"), 80),
            "sealed_at": _clean_text(scan.get("sealedAt"), 80),
            "producer": {
                "name": _clean_text(producer.get("name"), 100),
                "version": _clean_text(producer.get("version"), 40),
            },
            "target": {
                "kind": _clean_text(target.get("kind"), 40),
                "display_name": _clean_text(target.get("displayName"), 200),
                "revision": _clean_text(target.get("revision"), 120),
            },
            "mode": _clean_text(coverage_doc.payload.get("mode"), 40),
            "coverage": coverage_value,
            "finding_count": len(normalized),
            "severity_counts": severity_counts,
            "findings": normalized[:requested_limit],
            "findings_truncated": len(normalized) > requested_limit,
            "integrity_verified": True,
            "trust": "external_scan_result",
            "usage_policy": "review_only_never_execute",
        }


def _read_document(scan_dir: Path, relative_name: str) -> _CheckedDocument:
    reference = _safe_reference(relative_name, relative_name)
    path = scan_dir / reference
    try:
        before = path.lstat()
    except OSError as exc:
        raise CodexResultError(f"Unable to read required artifact {reference}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise CodexResultError(f"{reference} must be a non-symlink regular file")
    if before.st_size > MAX_DOCUMENT_BYTES:
        raise CodexResultError(f"{reference} exceeds the document size limit")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CodexResultError(f"Unable to open required artifact {reference}") from exc
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise CodexResultError(f"{reference} changed before it was opened")
        chunks: list[bytes] = []
        remaining = MAX_DOCUMENT_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(descriptor)
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise CodexResultError(f"{reference} exceeds the document size limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CodexResultError(f"{reference} is not valid UTF-8 JSON") from exc
    _validate_json_nesting(text, reference)
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise CodexResultError(f"{reference} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise CodexResultError(f"{reference} must contain a JSON object")
    _validate_json_limits(payload, reference)
    return _CheckedDocument(payload=payload, digest=hashlib.sha256(raw).hexdigest())


def _validate_json_nesting(text: str, reference: str) -> None:
    """Reject excessive container nesting before invoking the JSON decoder."""
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise CodexResultError(f"{reference} exceeds the JSON depth limit")
        elif character in "]}":
            depth -= 1


def _validate_json_limits(payload: dict[str, Any], reference: str) -> None:
    """Bound parsed JSON breadth and total work using an iterative walk."""
    nodes = 0
    stack: list[tuple[Any, int]] = [(payload, 1)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise CodexResultError(f"{reference} exceeds the JSON node limit")
        if depth > MAX_JSON_DEPTH:
            raise CodexResultError(f"{reference} exceeds the JSON depth limit")
        if isinstance(value, dict):
            if len(value) > MAX_JSON_CONTAINER_ITEMS:
                raise CodexResultError(f"{reference} exceeds the JSON container item limit")
            stack.extend((nested, depth + 1) for nested in value.values())
        elif isinstance(value, list):
            if len(value) > MAX_JSON_CONTAINER_ITEMS:
                raise CodexResultError(f"{reference} exceeds the JSON container item limit")
            stack.extend((nested, depth + 1) for nested in value)


def _verify_artifact_digest(scan: dict[str, Any], path: str, actual: str) -> None:
    artifacts = scan.get("artifacts")
    if not isinstance(artifacts, list):
        raise CodexResultError("Scan manifest is missing its sealed artifact list")
    expected = ""
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("path") == path:
            expected = str(artifact.get("sha256", ""))
            break
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not hmac_compare(actual, expected):
        raise CodexResultError(f"Integrity check failed for {path}")


def _require_document_type(payload: dict[str, Any], expected: str) -> None:
    if payload.get("documentType") != expected or payload.get("schemaVersion") != "1.0":
        raise CodexResultError(f"Unsupported Codex Security document: expected {expected} v1.0")


def _safe_reference(value: Any, default: str) -> str:
    reference = str(value or default)
    if reference not in {"findings.json", "coverage.json", "scan-manifest.json"}:
        raise CodexResultError("Manifest contains an unsupported artifact reference")
    return reference


def _normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
    severity = item.get("severity") if isinstance(item.get("severity"), dict) else {}
    severity_level = str(severity.get("level", "unknown")).lower()
    if severity_level not in ALLOWED_SEVERITIES:
        severity_level = "unknown"
    locations = item.get("locations") if isinstance(item.get("locations"), list) else []
    normalized_locations = []
    for location in locations[:5]:
        if not isinstance(location, dict):
            continue
        safe_path = _safe_location_path(location.get("path"))
        if not safe_path:
            continue
        normalized_locations.append(
            {
                "path": safe_path,
                "start_line": _safe_line(location.get("startLine")),
                "end_line": _safe_line(location.get("endLine")),
            }
        )
    taxonomy = item.get("taxonomy") if isinstance(item.get("taxonomy"), dict) else {}
    cwe = taxonomy.get("cwe") if isinstance(taxonomy.get("cwe"), list) else []
    return {
        "finding_id": _clean_text(item.get("findingId"), 120),
        "rule_id": _clean_text(item.get("ruleId"), 160),
        "title": _clean_text(item.get("title"), 300),
        "summary": _clean_text(item.get("summary"), 800),
        "severity": severity_level,
        "score": _safe_score(severity.get("score")),
        "remediation": _clean_text(item.get("remediation"), 800),
        "category": _clean_text(taxonomy.get("category"), 120),
        "cwe": [_clean_text(value, 40) for value in cwe[:10] if _clean_text(value, 40)],
        "locations": normalized_locations,
    }


def _clean_text(value: Any, limit: int) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(str(value or "")))
    text = "".join(
        character
        for character in text
        if character not in _UNSAFE_FORMAT_CHARS
        and (character in "\n\t" or unicodedata.category(character) not in {"Cc", "Cf", "Cs"})
    )
    text = re.sub(r"<[^>]{0,500}>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _safe_location_path(value: Any) -> str:
    text = str(value or "")
    if not text or "\\" in text or "\x00" in text or re.match(r"^[A-Za-z]:", text):
        return ""
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        return ""
    return _clean_text(path.as_posix(), 300)


def _safe_line(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        line = int(value)
    except (TypeError, ValueError):
        return None
    return line if 1 <= line <= 10_000_000 else None


def _safe_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 10 else None


def _is_contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _mtime_or_zero(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


def hmac_compare(left: str, right: str) -> bool:
    # hashlib values are public, but compare_digest avoids accidental
    # early-exit behavior and keeps the validation primitive consistent.
    import hmac

    return hmac.compare_digest(left, right)
