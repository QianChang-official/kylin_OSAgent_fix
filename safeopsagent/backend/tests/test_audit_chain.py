"""Tamper-evidence regression tests for the audit hash chain.

Each test here backs a specific sentence in the README. If a claim about the
audit log cannot be traced to a test in this file, the claim should not be
made.
"""
import sqlite3

import pytest

from backend import config
from backend.audit import chain
from backend.audit.logger import AuditLogger, AuditWriteError


def _entry(n: int) -> dict:
    return {
        "session_id": "s1",
        "request_id": f"req-{n}",
        "user_input": f"check disk usage {n}",
        "intent": "diagnose",
        "selected_tool": "disk_usage",
        "security_decision": "allow",
        "executed": True,
        "execution_success": True,
        "final_response": f"disk ok {n}",
    }


def _write(logger: AuditLogger, count: int = 3) -> None:
    for n in range(count):
        assert logger.log(_entry(n))


def _rows(db_path, table: str) -> list:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def _only_audit_table(db_path) -> str:
    with sqlite3.connect(str(db_path)) as conn:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'audit_2%'")]
    assert len(names) == 1
    return names[0]


# --- integrity -------------------------------------------------------------

def test_clean_chain_verifies(tmp_path):
    logger = AuditLogger(tmp_path / "audit.db")
    _write(logger, 5)

    report = logger.verify_chain()

    assert report["integrity_ok"] is True
    assert report["records"] == 5
    assert report["chained"] == 5
    assert report["first_break"] is None


def test_first_record_starts_from_genesis(tmp_path):
    logger = AuditLogger(tmp_path / "audit.db")
    _write(logger, 1)

    rows = _rows(tmp_path / "audit.db", _only_audit_table(tmp_path / "audit.db"))

    assert rows[0]["prev_hash"] == chain.GENESIS


def test_modified_record_is_detected(tmp_path):
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)
    _write(logger, 3)
    table = _only_audit_table(db)

    with sqlite3.connect(str(db)) as conn:
        conn.execute(f"UPDATE {table} SET security_decision = 'allow' WHERE request_id = 'req-1'")
        conn.execute(f"UPDATE {table} SET final_response = 'nothing happened' WHERE request_id = 'req-1'")

    report = logger.verify_chain()

    assert report["integrity_ok"] is False
    assert report["first_break"]["reason"] == "record content modified"
    assert report["first_break"]["request_id"] == "req-1"


def test_deleted_record_is_detected(tmp_path):
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)
    _write(logger, 4)
    table = _only_audit_table(db)

    with sqlite3.connect(str(db)) as conn:
        conn.execute(f"DELETE FROM {table} WHERE request_id = 'req-1'")

    report = logger.verify_chain()

    assert report["integrity_ok"] is False
    assert report["first_break"]["reason"] == "broken link (record deleted or reordered)"
    assert report["first_break"]["request_id"] == "req-2"


def test_truncated_tail_is_detected(tmp_path):
    """Deleting the newest records leaves the rest internally consistent."""
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)
    _write(logger, 4)
    table = _only_audit_table(db)

    with sqlite3.connect(str(db)) as conn:
        conn.execute(f"DELETE FROM {table} WHERE request_id IN ('req-2', 'req-3')")

    report = logger.verify_chain()

    assert report["integrity_ok"] is False
    assert report["first_break"]["reason"] == "chain head does not match last record (tail truncated)"


def test_chain_continues_across_daily_tables(tmp_path):
    """A dropped day's table must not verify as clean."""
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)

    logger._table_name = lambda: "audit_20260730"
    _write(logger, 2)
    logger._table_name = lambda: "audit_20260731"
    _write(logger, 2)

    assert logger.verify_chain()["integrity_ok"] is True

    with sqlite3.connect(str(db)) as conn:
        conn.execute("DROP TABLE audit_20260730")

    report = logger.verify_chain()
    assert report["integrity_ok"] is False


def test_stripping_chain_fields_is_detected(tmp_path):
    """Blanking the chain columns must not look like a pre-migration record."""
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)
    _write(logger, 3)
    table = _only_audit_table(db)

    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            f"UPDATE {table} SET entry_hash = NULL, prev_hash = NULL, payload_digest = NULL "
            f"WHERE request_id = 'req-1'"
        )

    report = logger.verify_chain()

    assert report["integrity_ok"] is False
    assert report["first_break"]["reason"] == "chain fields removed"


def test_records_written_before_the_migration_verify_as_legacy(tmp_path):
    """Upgrading must not make existing history look like an attack."""
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)
    _write(logger, 2)
    table = _only_audit_table(db)

    # Simulate rows that predate the chain columns: a contiguous prefix with
    # no chain fields, and a head that was never advanced for them.
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            f"UPDATE {table} SET entry_hash = NULL, prev_hash = NULL, "
            f"payload_digest = NULL, signature = NULL"
        )
        conn.execute("DELETE FROM audit_chain_head")

    report = logger.verify_chain()

    assert report["integrity_ok"] is True
    assert report["unchained_legacy"] == 2
    assert report["chained"] == 0


# --- authenticity ----------------------------------------------------------

def test_unsigned_chain_never_claims_authenticity(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIT_HMAC_KEY", "")
    logger = AuditLogger(tmp_path / "audit.db")
    _write(logger, 2)

    report = logger.verify_chain()

    assert report["integrity_ok"] is True
    assert report["authenticity"] == "unsigned"


def test_signed_chain_reports_authenticity_separately(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIT_HMAC_KEY", "test-key-not-for-production")
    logger = AuditLogger(tmp_path / "audit.db")
    _write(logger, 2)

    report = logger.verify_chain()

    assert report["integrity_ok"] is True
    assert report["authenticity"] == "verified"


def test_forged_rebuild_without_the_key_is_detected(tmp_path, monkeypatch):
    """The attack the hash chain alone cannot stop, and the key can.

    An attacker with database write access edits a record and recomputes every
    downstream digest and link, producing a chain that is internally perfect.
    Without the HMAC key the signatures cannot be regenerated.
    """
    monkeypatch.setattr(config, "AUDIT_HMAC_KEY", "test-key-not-for-production")
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)
    _write(logger, 3)
    table = _only_audit_table(db)

    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
        rows[1]["final_response"] = "nothing happened"
        prev = chain.GENESIS
        for row in rows:
            digest = chain.payload_digest(row)
            entry_hash = chain.link(prev, digest)
            conn.execute(
                f"UPDATE {table} SET final_response = ?, payload_digest = ?, "
                f"prev_hash = ?, entry_hash = ? WHERE id = ?",
                (row["final_response"], digest, prev, entry_hash, row["id"]),
            )
            prev = entry_hash
        conn.execute("UPDATE audit_chain_head SET head = ? WHERE id = 1", (prev,))

    report = logger.verify_chain()

    assert report["authenticity"] == "failed"
    assert report["first_break"]["reason"] == "signature mismatch"


def test_the_same_forgery_is_invisible_without_a_key(tmp_path, monkeypatch):
    """States the boundary as a test, so the README cannot overclaim it."""
    monkeypatch.setattr(config, "AUDIT_HMAC_KEY", "")
    db = tmp_path / "audit.db"
    logger = AuditLogger(db)
    _write(logger, 3)
    table = _only_audit_table(db)

    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
        rows[1]["final_response"] = "nothing happened"
        prev = chain.GENESIS
        for row in rows:
            digest = chain.payload_digest(row)
            entry_hash = chain.link(prev, digest)
            conn.execute(
                f"UPDATE {table} SET final_response = ?, payload_digest = ?, "
                f"prev_hash = ?, entry_hash = ? WHERE id = ?",
                (row["final_response"], digest, prev, entry_hash, row["id"]),
            )
            prev = entry_hash
        conn.execute("UPDATE audit_chain_head SET head = ? WHERE id = 1", (prev,))

    report = logger.verify_chain()

    # Unsigned, a full rebuild is indistinguishable from honest history. This
    # is why AUDIT_HMAC_KEY exists and why the docs must not claim otherwise.
    assert report["integrity_ok"] is True
    assert report["authenticity"] == "unsigned"


# --- fail-closed -----------------------------------------------------------

def test_audit_write_failure_raises_instead_of_being_swallowed(tmp_path):
    """INV-R2: a request must not succeed while its audit record is lost."""
    logger = AuditLogger(tmp_path / "audit.db")
    unwritable = tmp_path / "not-a-database"
    unwritable.mkdir()
    logger.db_path = unwritable

    with pytest.raises(AuditWriteError):
        logger.log(_entry(0))


def test_preflight_raises_before_a_side_effect(tmp_path):
    logger = AuditLogger(tmp_path / "audit.db")
    logger.preflight()

    unwritable = tmp_path / "also-not-a-database"
    unwritable.mkdir()
    logger.db_path = unwritable

    with pytest.raises(AuditWriteError):
        logger.preflight()
