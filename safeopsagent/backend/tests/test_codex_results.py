import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.security import codex_results as codex_results_module
from backend.security.codex_results import (
    MAX_JSON_CONTAINER_ITEMS,
    MAX_JSON_DEPTH,
    MAX_JSON_NODES,
    MAX_SCAN_DIRECTORY_ENTRIES,
    CodexResultError,
    CodexResultStore,
)


def _write_json(path: Path, payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _build_scan(root: Path, directory_id: str = "scan-001") -> Path:
    scan_dir = root / directory_id
    scan_dir.mkdir(parents=True)
    findings = {
        "documentType": "codex-security.findings",
        "schemaVersion": "1.0",
        "scanId": "scan_actual_001",
        "findings": [
            {
                "findingId": "finding-1",
                "ruleId": "path-traversal.archive-extraction",
                "title": "Unsafe\u202e archive <b>write</b>",
                "summary": "A path escapes the destination.",
                "severity": {"level": "high", "score": 8.1},
                "taxonomy": {"category": "path-traversal", "cwe": ["CWE-22"]},
                "locations": [
                    {"path": "src/extract.py", "startLine": 41, "endLine": 44},
                    {"path": "../../outside", "startLine": 1},
                ],
                "remediation": "Validate containment.",
                "evidence": "rm -rf / must never be returned by the summary API",
            }
        ],
    }
    coverage = {
        "documentType": "codex-security.coverage",
        "schemaVersion": "1.0",
        "scanId": "scan_actual_001",
        "mode": "repository",
        "completeness": "complete",
        "deferred": [],
    }
    findings_hash = _write_json(scan_dir / "findings.json", findings)
    coverage_hash = _write_json(scan_dir / "coverage.json", coverage)
    manifest = {
        "documentType": "codex-security.scan-manifest",
        "schemaVersion": "1.0",
        "scan": {
            "id": "scan_actual_001",
            "status": "completed",
            "completedAt": "2026-07-30T07:00:00Z",
            "sealedAt": "2026-07-30T07:00:01Z",
            "producer": {"name": "codex-security-plugin", "version": "0.1.4"},
            "target": {
                "kind": "git_worktree",
                "displayName": "safeopsagent",
                "revision": "abc123",
            },
            "findingsRef": "findings.json",
            "coverageRef": "coverage.json",
            "artifacts": [
                {"path": "findings.json", "sha256": findings_hash},
                {"path": "coverage.json", "sha256": coverage_hash},
            ],
        },
    }
    _write_json(scan_dir / "scan-manifest.json", manifest)
    return scan_dir


def _replace_artifact(scan_dir: Path, name: str, payload: dict) -> None:
    digest = _write_json(scan_dir / name, payload)
    manifest_path = scan_dir / "scan-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for artifact in manifest["scan"]["artifacts"]:
        if artifact["path"] == name:
            artifact["sha256"] = digest
            break
    _write_json(manifest_path, manifest)


def test_imports_hash_verified_summary_without_raw_evidence(tmp_path):
    result_root = tmp_path / "results"
    _build_scan(result_root)
    store = CodexResultStore(result_root, tmp_path / "project")

    result = store.load("scan-001")

    assert result["integrity_verified"] is True
    assert result["authenticity_verified"] is False
    assert result["trust_basis"] == "manifest_hash_consistency_and_private_directory_acl"
    assert result["finding_count"] == 1
    assert result["coverage"] == "complete"
    assert result["severity_counts"]["high"] == 1
    finding = result["findings"][0]
    assert finding["title"] == "Unsafe archive write"
    assert finding["locations"] == [
        {"path": "src/extract.py", "start_line": 41, "end_line": 44}
    ]
    assert "evidence" not in finding
    assert "rm -rf" not in json.dumps(result)


def test_tampered_artifact_is_rejected(tmp_path):
    result_root = tmp_path / "results"
    scan_dir = _build_scan(result_root)
    (scan_dir / "findings.json").write_text("{}", encoding="utf-8")
    store = CodexResultStore(result_root, tmp_path / "project")

    with pytest.raises(CodexResultError, match="Integrity check failed"):
        store.load("scan-001")


def test_scan_identifier_cannot_escape_result_root(tmp_path):
    store = CodexResultStore(tmp_path / "results", tmp_path / "project")

    with pytest.raises(CodexResultError, match="Invalid scan"):
        store.load("../outside")


def test_result_root_must_be_outside_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(CodexResultError, match="outside the project"):
        CodexResultStore(project / "results", project)


def test_result_root_symlink_is_rejected(tmp_path):
    real_root = tmp_path / "real-results"
    real_root.mkdir()
    link = tmp_path / "linked-results"
    try:
        link.symlink_to(real_root, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable in this environment")

    with pytest.raises(CodexResultError, match="result root must not be a symbolic link"):
        CodexResultStore(link, tmp_path / "project")


def test_lists_only_valid_completed_scans(tmp_path):
    result_root = tmp_path / "results"
    _build_scan(result_root, "scan-001")
    invalid = result_root / "incomplete"
    invalid.mkdir()
    (invalid / "scan-manifest.json").write_text("{}", encoding="utf-8")
    store = CodexResultStore(result_root, tmp_path / "project")

    scans = store.list_scans()

    assert [scan["directory_id"] for scan in scans] == ["scan-001"]


def test_scan_directory_symlink_is_rejected(tmp_path):
    result_root = tmp_path / "results"
    real_scan = _build_scan(tmp_path / "elsewhere", "real-scan")
    result_root.mkdir()
    link = result_root / "linked-scan"
    try:
        link.symlink_to(real_scan, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable in this environment")
    store = CodexResultStore(result_root, tmp_path / "project")

    with pytest.raises(CodexResultError, match="symbolic link"):
        store.load("linked-scan")


def test_excessive_json_nesting_is_rejected_before_import(tmp_path):
    result_root = tmp_path / "results"
    scan_dir = _build_scan(result_root)
    coverage = json.loads((scan_dir / "coverage.json").read_text(encoding="utf-8"))
    nested: dict = {}
    for _ in range(MAX_JSON_DEPTH + 1):
        nested = {"child": nested}
    coverage["untrustedExtension"] = nested
    _replace_artifact(scan_dir, "coverage.json", coverage)
    store = CodexResultStore(result_root, tmp_path / "project")

    with pytest.raises(CodexResultError, match="JSON depth limit"):
        store.load("scan-001")


def test_oversized_json_container_is_rejected(tmp_path):
    result_root = tmp_path / "results"
    scan_dir = _build_scan(result_root)
    coverage = json.loads((scan_dir / "coverage.json").read_text(encoding="utf-8"))
    coverage["untrustedExtension"] = [None] * (MAX_JSON_CONTAINER_ITEMS + 1)
    _replace_artifact(scan_dir, "coverage.json", coverage)
    store = CodexResultStore(result_root, tmp_path / "project")

    with pytest.raises(CodexResultError, match="JSON container item limit"):
        store.load("scan-001")


def test_excessive_total_json_nodes_are_rejected(tmp_path):
    result_root = tmp_path / "results"
    scan_dir = _build_scan(result_root)
    coverage = json.loads((scan_dir / "coverage.json").read_text(encoding="utf-8"))
    per_bucket = MAX_JSON_CONTAINER_ITEMS - 1
    bucket_count = (MAX_JSON_NODES // per_bucket) + 1
    coverage["untrustedExtension"] = {
        f"bucket-{index}": [0] * per_bucket for index in range(bucket_count)
    }
    _replace_artifact(scan_dir, "coverage.json", coverage)
    store = CodexResultStore(result_root, tmp_path / "project")

    with pytest.raises(CodexResultError, match="JSON node limit"):
        store.load("scan-001")


def test_codex_result_api_reports_unconfigured_store(monkeypatch):
    monkeypatch.setattr(app_module.config, "CODEX_SECURITY_RESULTS_DIR", "")

    response = TestClient(app_module.app).get("/security/codex/scans")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "scans": [],
        "discovery_limited": False,
        "discovery_limit_reasons": [],
        "entries_examined": 0,
    }


def test_codex_result_api_lists_and_loads_verified_scan(tmp_path, monkeypatch):
    result_root = tmp_path / "results"
    _build_scan(result_root)
    monkeypatch.setattr(
        app_module.config,
        "CODEX_SECURITY_RESULTS_DIR",
        str(result_root),
    )
    client = TestClient(app_module.app)

    listing = client.get("/security/codex/scans?limit=10")
    detail = client.get("/security/codex/scans/scan-001?finding_limit=1")

    assert listing.status_code == 200
    assert listing.json()["configured"] is True
    assert listing.json()["scans"][0]["integrity_verified"] is True
    assert detail.status_code == 200
    assert detail.json()["scan_id"] == "scan_actual_001"
    assert detail.json()["findings"][0]["severity"] == "high"


def test_codex_result_api_rejects_tampered_or_escaping_scan(tmp_path, monkeypatch):
    result_root = tmp_path / "results"
    scan_dir = _build_scan(result_root)
    (scan_dir / "findings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        app_module.config,
        "CODEX_SECURITY_RESULTS_DIR",
        str(result_root),
    )
    client = TestClient(app_module.app)

    tampered = client.get("/security/codex/scans/scan-001")
    escaping = client.get("/security/codex/scans/%2E%2E%5Coutside")

    assert tampered.status_code == 422
    assert escaping.status_code in {404, 422}


def test_scan_directory_enumeration_has_a_fixed_work_budget(tmp_path, monkeypatch):
    result_root = tmp_path / "results"
    result_root.mkdir()
    store = CodexResultStore(result_root, tmp_path / "project")
    yielded = 0

    def bounded_entries(_path):
        nonlocal yielded
        for index in range(MAX_SCAN_DIRECTORY_ENTRIES + 1):
            yielded += 1
            yield result_root / f"invalid-{index}"
        raise AssertionError("list_scans consumed beyond its directory-entry budget")

    monkeypatch.setattr(Path, "iterdir", bounded_entries)

    page = store.list_scans_page(limit=1)

    assert page["scans"] == []
    assert page["discovery_limited"] is True
    assert page["discovery_limit_reasons"] == ["directory_entry_budget"]
    assert page["entries_examined"] == MAX_SCAN_DIRECTORY_ENTRIES
    assert yielded == MAX_SCAN_DIRECTORY_ENTRIES + 1


def test_scan_listing_stops_at_total_document_byte_budget(tmp_path, monkeypatch):
    result_root = tmp_path / "results"
    _build_scan(result_root)
    store = CodexResultStore(result_root, tmp_path / "project")
    monkeypatch.setattr(codex_results_module, "MAX_SCAN_LIST_BYTES", 1)

    page = store.list_scans_page(limit=10)

    assert page["scans"] == []
    assert page["discovery_limited"] is True
    assert page["discovery_limit_reasons"] == ["document_byte_budget"]


def test_codex_result_api_exposes_discovery_budget_status(tmp_path, monkeypatch):
    result_root = tmp_path / "results"
    _build_scan(result_root)
    monkeypatch.setattr(app_module.config, "CODEX_SECURITY_RESULTS_DIR", str(result_root))
    monkeypatch.setattr(codex_results_module, "MAX_SCAN_LIST_BYTES", 1)

    response = TestClient(app_module.app).get("/security/codex/scans")

    assert response.status_code == 200
    assert response.json()["discovery_limited"] is True
    assert response.json()["discovery_limit_reasons"] == ["document_byte_budget"]
