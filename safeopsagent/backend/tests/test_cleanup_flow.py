import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.audit.logger import AuditLogger
from backend.cleanup.service import CleanupError, CleanupService
import backend.cleanup.service as cleanup_service_module


def _old_file(path, content="temporary"):
    path.write_text(content, encoding="utf-8")
    old = time.time() - 48 * 3600
    os.utime(path, (old, old))
    return path


def test_cleanup_scan_only_returns_safe_old_candidates(tmp_path):
    _old_file(tmp_path / "old.tmp")
    _old_file(tmp_path / "ignored.txt")
    (tmp_path / "new.log").write_text("new", encoding="utf-8")
    service = CleanupService(allowed_roots=(tmp_path,))

    result = service.scan(str(tmp_path), min_age_hours=24, max_files=10)

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["path"].endswith("old.tmp")
    assert result["dry_run"] is True
    assert result["permanent_delete"] is False


def test_cleanup_rejects_outside_root_and_symlink(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    service = CleanupService(allowed_roots=(allowed,))

    with pytest.raises(CleanupError, match="outside allowed roots"):
        service.scan(str(outside))

    target = _old_file(outside / "target.tmp")
    link = allowed / "linked.tmp"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable in this environment")
    result = service.scan(str(allowed))
    assert result["candidate_count"] == 0


def test_cleanup_rejects_filesystem_root_even_if_configured(tmp_path):
    filesystem_root = Path(tmp_path.anchor)
    service = CleanupService(allowed_roots=(filesystem_root,))

    with pytest.raises(CleanupError, match="outside allowed roots"):
        service.scan(str(filesystem_root))


def test_cleanup_rejects_hard_link_candidate(tmp_path):
    original = _old_file(tmp_path / "source.tmp")
    hardlink = tmp_path / "linked.tmp"
    try:
        os.link(original, hardlink)
    except OSError:
        pytest.skip("hard links are unavailable in this environment")
    service = CleanupService(allowed_roots=(tmp_path,))

    result = service.scan(str(tmp_path))

    assert result["candidate_count"] == 0
    assert any("hard-linked" in warning for warning in result["warnings"])


def test_cleanup_plan_quarantine_restore_is_reversible(tmp_path):
    original = _old_file(tmp_path / "recover.tmp", "recover me")
    service = CleanupService(allowed_roots=(tmp_path,))
    plan = service.create_plan(str(tmp_path), min_age_hours=24, max_files=10)

    quarantined = service.quarantine(plan["plan_id"], plan["plan_hash"])
    assert not original.exists()
    assert quarantined["moved_count"] == 1
    assert quarantined["permanent_delete"] is False

    restored = service.restore(
        quarantined["quarantine_id"],
        quarantined["manifest_hash"],
    )
    assert original.read_text(encoding="utf-8") == "recover me"
    assert restored["restored_count"] == 1
    with pytest.raises(CleanupError, match="already been restored"):
        service.restore(quarantined["quarantine_id"], quarantined["manifest_hash"])


def test_cleanup_nested_scan_root_uses_controlled_allowed_root_quarantine(tmp_path):
    nested = tmp_path / "job"
    nested.mkdir()
    original = _old_file(nested / "nested.tmp")
    service = CleanupService(allowed_roots=(tmp_path,))
    plan = service.create_plan(str(nested), min_age_hours=24, max_files=10)

    quarantined = service.quarantine(plan["plan_id"], plan["plan_hash"])
    assert not original.exists()
    assert str(tmp_path / ".safeopsagent-quarantine") in quarantined["items"][0]["quarantine_path"]
    restored = service.restore(quarantined["quarantine_id"], quarantined["manifest_hash"])
    assert restored["restored_count"] == 1
    assert original.exists()


def test_cleanup_rejects_toctou_metadata_change_and_plan_replay(tmp_path):
    candidate = _old_file(tmp_path / "change.tmp", "before")
    service = CleanupService(allowed_roots=(tmp_path,))
    plan = service.create_plan(str(tmp_path), min_age_hours=24, max_files=10)
    candidate.write_text("after", encoding="utf-8")

    with pytest.raises(CleanupError, match="metadata changed"):
        service.quarantine(plan["plan_id"], plan["plan_hash"])
    with pytest.raises(CleanupError, match="already been used"):
        service.quarantine(plan["plan_id"], plan["plan_hash"])


def test_cleanup_rolls_back_identity_swap_during_atomic_move(monkeypatch, tmp_path):
    candidate = _old_file(tmp_path / "race.tmp", "original")
    service = CleanupService(allowed_roots=(tmp_path,))
    plan = service.create_plan(str(tmp_path), min_age_hours=24, max_files=10)
    real_replace = os.replace
    injected = False

    def raced_replace(source, destination):
        nonlocal injected
        source_path = os.fspath(source)
        destination_path = os.fspath(destination)
        if (
            not injected
            and source_path == os.fspath(candidate)
            and ".safeopsagent-quarantine" in destination_path
        ):
            injected = True
            real_replace(source, tmp_path / "attacker-held.tmp")
            candidate.write_text("replacement", encoding="utf-8")
        return real_replace(source, destination)

    monkeypatch.setattr(cleanup_service_module.os, "replace", raced_replace)

    with pytest.raises(CleanupError, match="metadata changed"):
        service.quarantine(plan["plan_id"], plan["plan_hash"])

    assert candidate.read_text(encoding="utf-8") == "replacement"
    with pytest.raises(CleanupError, match="already been used"):
        service.quarantine(plan["plan_id"], plan["plan_hash"])


def test_cleanup_plan_expiry(tmp_path):
    clock = [1000.0]
    _old_file(tmp_path / "expired.tmp")
    service = CleanupService(allowed_roots=(tmp_path,), now_fn=lambda: clock[0])
    plan = service.create_plan(str(tmp_path), min_age_hours=1, max_files=10)
    clock[0] = plan["expires_at"] + 1

    with pytest.raises(CleanupError, match="expired"):
        service.quarantine(plan["plan_id"], plan["plan_hash"])


def test_cleanup_http_confirm_audit_chain(monkeypatch, tmp_path):
    original = _old_file(tmp_path / "api.tmp", "api")
    service = CleanupService(allowed_roots=(tmp_path,))
    monkeypatch.setattr(cleanup_service_module, "_service", service)
    app_module._confirmations.clear()
    logger = AuditLogger(tmp_path / "audit.db")
    monkeypatch.setattr(app_module, "get_logger", lambda: logger)
    client = TestClient(app_module.app)

    plan_response = client.post(
        "/tools/call",
        json={
            "tool_name": "safe_cleanup_plan",
            "arguments": {"path": str(tmp_path), "min_age_hours": 24, "max_files": 10},
            "session_id": "cleanup-e2e",
        },
    ).json()
    plan = plan_response["result"]["data"]
    dry_run = client.post(
        "/tools/call",
        json={
            "tool_name": "safe_cleanup_quarantine",
            "arguments": {"plan_id": plan["plan_id"], "plan_hash": plan["plan_hash"]},
            "session_id": "cleanup-e2e",
        },
    ).json()

    assert dry_run["security_decision"] == "confirm"
    assert dry_run["confirmation_required"] is True
    assert original.exists()

    confirmed = client.post(
        "/tools/confirm",
        json={
            "confirmation_token": dry_run["confirmation_token"],
            "session_id": "cleanup-e2e",
        },
    ).json()
    assert confirmed["success"] is True
    assert confirmed["original_request_id"] == dry_run["request_id"]
    assert not original.exists()
    trace = logger.trace(confirmed["request_id"])
    assert trace["found"] is True
    assert any(event["stage"] == "confirmation" for event in trace["trace"]["events"])

    replay = client.post(
        "/tools/confirm",
        json={"confirmation_token": dry_run["confirmation_token"]},
    ).json()
    assert replay["success"] is False
    assert replay["security_reason"] == "confirmation_token_used"
