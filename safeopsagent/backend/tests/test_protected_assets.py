"""SafeOpsAgent's own irreplaceable assets must be unreachable by cleanup."""
from pathlib import Path

import pytest

from backend import config
from backend.cleanup.service import CleanupError, CleanupService


def test_protected_roots_are_dropped_from_the_allowlist():
    service = CleanupService(
        allowed_roots=(
            config.PROJECT_DIR,
            config.PROJECT_DIR / "data",
            config.DECEPTION_EVIDENCE_DIR,
        )
    )

    assert service.allowed_roots == ()


def test_scanning_a_protected_directory_is_refused(tmp_path, monkeypatch):
    protected = tmp_path / "precious"
    protected.mkdir()
    monkeypatch.setattr(config, "PROTECTED_ASSET_PATHS", (protected,))
    service = CleanupService(allowed_roots=(tmp_path,))

    with pytest.raises(CleanupError, match="protected SafeOpsAgent asset"):
        service.scan(str(protected))


def test_audit_database_and_evidence_are_protected_by_default():
    service = CleanupService(allowed_roots=("/tmp",))

    assert service._is_protected_asset(config.AUDIT_DB_PATH) is True
    assert service._is_protected_asset(config.DECEPTION_EVIDENCE_DIR / "incidents.jsonl") is True
    assert service._is_protected_asset(Path(config.BASE_DIR) / "static" / "console" / "index.html") is True


def test_unrelated_temporary_paths_stay_eligible(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROTECTED_ASSET_PATHS", (tmp_path / "keep",))

    service = CleanupService(allowed_roots=(tmp_path,))

    assert service._is_protected_asset(tmp_path / "scratch" / "session.tmp") is False
    assert service.allowed_roots == (tmp_path.resolve(),)
