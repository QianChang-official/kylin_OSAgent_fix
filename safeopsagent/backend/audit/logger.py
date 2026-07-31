"""SQLite audit logger with backward-compatible Trace v2 fields."""
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
from threading import Lock

from backend import config
from backend.audit import chain


AUDIT_V2_COLUMNS = {
    "risk_score": "INTEGER",
    "risk_level_text": "TEXT",
    "legacy_risk_level": "INTEGER",
    "security_decision": "TEXT",
    "security_reason": "TEXT",
    "matched_rules": "TEXT",
    "actual_command": "TEXT",
    "executor_user": "TEXT",
    "execution_success": "INTEGER",
    "stdout_summary": "TEXT",
    "stderr_summary": "TEXT",
    "full_trace_json": "TEXT",
}

# Tamper-evidence columns. Split from AUDIT_V2_COLUMNS because rows written
# before this migration have no chain fields: they verify as "unchained"
# rather than as "broken", so an upgrade does not retroactively look like an
# attack. See backend/audit/chain.py for what these do and do not prove.
AUDIT_CHAIN_COLUMNS = {
    "payload_digest": "TEXT",
    "prev_hash": "TEXT",
    "entry_hash": "TEXT",
    "signature": "TEXT",
}

CHAIN_HEAD_TABLE = "audit_chain_head"

TEXT_LIMIT = 2000
TRACE_LIMIT = 8000
SUMMARY_LIMIT = 500


class AuditWriteError(RuntimeError):
    """Raised when an audit record could not be committed.

    INV-R2 requires every request to produce a replayable audit record. A
    caller that swallows this exception and still reports success violates
    that invariant, so the failure is raised rather than returned.
    """


class AuditLogger:
    def __init__(self, db_path: Path = config.AUDIT_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._key = config.AUDIT_HMAC_KEY.encode("utf-8") if config.AUDIT_HMAC_KEY else None
        self._ensure_table()

    def _table_name(self) -> str:
        return f"audit_{datetime.now().strftime('%Y%m%d')}"

    def _ensure_table(self):
        table = self._table_name()
        with closing(sqlite3.connect(str(self.db_path))) as conn, conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    session_id TEXT,
                    request_id TEXT,
                    user_input TEXT,
                    intent TEXT,
                    selected_tool TEXT,
                    tool_arguments TEXT,
                    risk_level INTEGER,
                    confirmation_required INTEGER,
                    executed INTEGER,
                    execution_result TEXT,
                    final_response TEXT,
                    rule_hits TEXT,
                    duration_ms INTEGER,
                    risk_score INTEGER,
                    risk_level_text TEXT,
                    legacy_risk_level INTEGER,
                    security_decision TEXT,
                    security_reason TEXT,
                    matched_rules TEXT,
                    actual_command TEXT,
                    executor_user TEXT,
                    execution_success INTEGER,
                    stdout_summary TEXT,
                    stderr_summary TEXT,
                    full_trace_json TEXT,
                    payload_digest TEXT,
                    prev_hash TEXT,
                    entry_hash TEXT,
                    signature TEXT
                )
            """)
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {CHAIN_HEAD_TABLE} (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    head TEXT NOT NULL
                )
            """)
            self._ensure_v2_columns(conn, table)
            conn.commit()

    def _ensure_v2_columns(self, conn, table_name: str):
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        for column, column_type in {**AUDIT_V2_COLUMNS, **AUDIT_CHAIN_COLUMNS}.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {column_type}")

    def _row_values(self, entry: dict) -> dict:
        """Project an entry onto the stored columns, in digest order."""
        trace_json = entry.get("full_trace_json") or self._build_trace(entry)
        return {
            "timestamp": datetime.now().isoformat(),
            "session_id": self._truncate(entry.get("session_id", "")),
            "request_id": self._truncate(entry.get("request_id", str(uuid.uuid4())[:8])),
            "user_input": self._truncate(entry.get("user_input", "")),
            "intent": self._truncate(entry.get("intent", "")),
            "selected_tool": self._truncate(entry.get("selected_tool", "")),
            "tool_arguments": self._safe_json(entry.get("tool_arguments", {})),
            "risk_level": entry.get("risk_level", 1),
            "confirmation_required": 1 if entry.get("confirmation_required") else 0,
            "executed": 1 if entry.get("executed") else 0,
            "execution_result": self._safe_json(entry.get("execution_result", {}), TEXT_LIMIT),
            "final_response": self._truncate(entry.get("final_response", ""), TEXT_LIMIT),
            "rule_hits": self._safe_json(entry.get("rule_hits", [])),
            "duration_ms": entry.get("duration_ms", 0),
            "risk_score": entry.get("risk_score"),
            "risk_level_text": self._truncate(entry.get("risk_level_text", "")),
            "legacy_risk_level": entry.get("legacy_risk_level", entry.get("risk_level", 1)),
            "security_decision": self._truncate(entry.get("security_decision", "")),
            "security_reason": self._truncate(entry.get("security_reason", "")),
            "matched_rules": self._safe_json(entry.get("matched_rules", [])),
            "actual_command": self._safe_json(entry.get("actual_command", [])),
            "executor_user": self._truncate(entry.get("executor_user", "")),
            "execution_success": 1 if entry.get("execution_success") else 0,
            "stdout_summary": self._truncate(entry.get("stdout_summary", ""), TEXT_LIMIT),
            "stderr_summary": self._truncate(entry.get("stderr_summary", ""), TEXT_LIMIT),
            "full_trace_json": self._safe_json(trace_json, TRACE_LIMIT),
        }

    def _read_head(self, conn) -> str:
        row = conn.execute(f"SELECT head FROM {CHAIN_HEAD_TABLE} WHERE id = 1").fetchone()
        return row[0] if row else chain.GENESIS

    def _write_head(self, conn, head: str) -> None:
        conn.execute(
            f"INSERT INTO {CHAIN_HEAD_TABLE} (id, head) VALUES (1, ?) "
            f"ON CONFLICT(id) DO UPDATE SET head = excluded.head",
            (head,),
        )

    def preflight(self) -> None:
        """Fail before a side effect if the audit log cannot be written.

        Called on the execution path so an unwritable audit store stops the
        request instead of producing an unrecorded action. This closes the
        window it can close: a failure *after* the tool has run cannot un-run
        it, which is why log() also raises rather than returning False.
        """
        try:
            with self._lock:
                self._ensure_table()
                with closing(sqlite3.connect(str(self.db_path))) as conn, conn:
                    conn.execute(f"SELECT 1 FROM {self._table_name()} LIMIT 1").fetchone()
                    self._read_head(conn)
        except Exception as exc:
            raise AuditWriteError(f"audit log is not writable: {exc}") from exc

    def log(self, entry: dict) -> bool:
        try:
            with self._lock:
                self._ensure_table()
                with closing(sqlite3.connect(str(self.db_path))) as conn, conn:
                    values = self._row_values(entry)
                    digest = chain.payload_digest(values)
                    prev_hash = self._read_head(conn)
                    entry_hash = chain.link(prev_hash, digest)
                    conn.execute(f"""
                        INSERT INTO {self._table_name()}
                        (timestamp, session_id, request_id, user_input, intent,
                         selected_tool, tool_arguments, risk_level, confirmation_required,
                         executed, execution_result, final_response, rule_hits, duration_ms,
                         risk_score, risk_level_text, legacy_risk_level, security_decision,
                         security_reason, matched_rules, actual_command, executor_user,
                         execution_success, stdout_summary, stderr_summary, full_trace_json,
                         payload_digest, prev_hash, entry_hash, signature)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        *[values[column] for column in chain.DIGEST_COLUMNS],
                        digest,
                        prev_hash,
                        entry_hash,
                        chain.sign(entry_hash, self._key),
                    ))
                    self._write_head(conn, entry_hash)
                    conn.commit()
            return True
        except Exception as exc:
            # Deliberately not swallowed: a dropped audit record with a
            # successful response is exactly the INV-R2 violation this
            # logger exists to prevent.
            raise AuditWriteError(f"failed to write audit log: {exc}") from exc

    def query(self, session_id: str = "", limit: int = 100) -> list:
        table = self._table_name()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if session_id:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [self._normalize_row(dict(row)) for row in rows]

    def trace(self, request_id: str) -> dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            for table in sorted(self._audit_tables(conn), reverse=True):
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE request_id = ? ORDER BY id DESC LIMIT 1",
                    (request_id,),
                ).fetchall()
                if rows:
                    row = self._normalize_row(dict(rows[0]))
                    trace = row.get("full_trace_json")
                    return {
                        "found": True,
                        "request_id": request_id,
                        "audit": row,
                        "trace": trace if isinstance(trace, dict) else self._json_loads(trace, {}),
                    }
        return {"found": False, "request_id": request_id, "audit": None, "trace": {}}

    def cleanup_old(self, days: int = config.AUDIT_RETENTION_DAYS) -> dict:
        return {
            "status": "retained",
            "message": "Audit cleanup is disabled; audit data is append-only.",
            "retention_days": days,
        }

    def clear_all(self) -> dict:
        return {
            "status": "retained",
            "message": "Audit clearing is disabled; audit data is append-only.",
        }

    def _audit_tables(self, conn) -> list[str]:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'audit_%'"
        )
        # audit_chain_head matches the LIKE pattern but holds chain state, not
        # records; callers that scan for a request_id must not see it.
        return [row[0] for row in cursor.fetchall() if row[0] != CHAIN_HEAD_TABLE]

    def verify_chain(self) -> dict:
        """Recompute the hash chain and report where it first breaks.

        Integrity and authenticity are reported separately because they are
        different claims. ``integrity_ok`` means the stored records still
        recompute to the stored links: an edit, a deletion, a reordering, or
        a dropped day's table shows up here. ``authenticity`` is only
        meaningful when an HMAC key is configured; without one, a writer who
        can reach the database can rebuild a consistent chain, so
        ``integrity_ok`` alone does not prove nobody rewrote history.
        """
        report = {
            "integrity_ok": True,
            "authenticity": "no_key" if not self._key else "verified",
            "records": 0,
            "chained": 0,
            "unchained_legacy": 0,
            "first_break": None,
            "boundary": (
                "Hash chain detects modification, deletion and reordering. "
                "Forgery by a writer with database access is only infeasible "
                "when AUDIT_HMAC_KEY is configured and held off this host."
            ),
        }

        def fail(reason, table, row_id, request_id):
            if report["first_break"] is None:
                report["integrity_ok"] = False
                report["first_break"] = {
                    "reason": reason,
                    "table": table,
                    "id": row_id,
                    "request_id": request_id,
                }

        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.row_factory = sqlite3.Row
            expected_prev = chain.GENESIS
            seen_chained = False
            for table in sorted(self._audit_tables(conn)):
                for row in conn.execute(f"SELECT * FROM {table} ORDER BY id ASC"):
                    row = dict(row)
                    report["records"] += 1
                    request_id = row.get("request_id")
                    if not row.get("entry_hash"):
                        # Records written before the chain migration. Accepted
                        # only as a contiguous prefix; stripping chain fields
                        # from a later record is treated as tampering.
                        if seen_chained:
                            fail("chain fields removed", table, row.get("id"), request_id)
                        else:
                            report["unchained_legacy"] += 1
                        continue
                    seen_chained = True
                    report["chained"] += 1
                    if row.get("prev_hash") != expected_prev:
                        fail("broken link (record deleted or reordered)",
                             table, row.get("id"), request_id)
                    digest = chain.payload_digest(row)
                    if digest != row.get("payload_digest"):
                        fail("record content modified", table, row.get("id"), request_id)
                    if chain.link(row.get("prev_hash") or "", digest) != row.get("entry_hash"):
                        fail("entry hash does not match content",
                             table, row.get("id"), request_id)
                    if self._key and not chain.signature_matches(
                        row.get("entry_hash") or "", row.get("signature") or "", self._key
                    ):
                        report["authenticity"] = "failed"
                        fail("signature mismatch", table, row.get("id"), request_id)
                    expected_prev = row.get("entry_hash")

            head = self._read_head(conn)
            if seen_chained and head != expected_prev:
                fail("chain head does not match last record (tail truncated)",
                     "audit_chain_head", 1, None)

        if report["chained"] and not self._key:
            report["authenticity"] = "unsigned"
        return report

    def _build_trace(self, entry: dict) -> dict:
        events = [
            {"stage": "receive_input", "summary": self._summary(entry.get("user_input", ""))},
        ]
        session_events = self._summary_list(entry.get("session_events", []))
        if session_events:
            events.append({
                "stage": "session_lifecycle",
                "events": session_events,
            })
        confirmation_events = self._summary_list(entry.get("confirmation_events", []))
        if confirmation_events:
            events.append({
                "stage": "confirmation",
                "events": confirmation_events,
                "original_request_id": self._summary(entry.get("original_request_id", "")),
            })
        events.extend([
            {
                "stage": "precheck",
                "risk_score": entry.get("risk_score"),
                "matched_rules": self._summary_list(entry.get("matched_rules", [])),
            },
            {
                "stage": "tool_selected",
                "selected_tool": self._summary(entry.get("selected_tool", "")),
                "intent": self._summary(entry.get("intent", "")),
            },
            {
                "stage": "args_validated",
                "tool_arguments": self._summarize_value(entry.get("tool_arguments", {})),
            },
            {
                "stage": "risk_scored",
                "risk_score": entry.get("risk_score"),
                "risk_level": self._summary(entry.get("risk_level_text", "")),
                "legacy_risk_level": entry.get("legacy_risk_level", entry.get("risk_level", 1)),
                "risk_factors": self._summary_list(entry.get("risk_factors", [])),
            },
            {
                "stage": "security_decision",
                "security_decision": self._summary(entry.get("security_decision", "")),
                "security_reason": self._summary(entry.get("security_reason", "")),
                "confirmation_required": bool(entry.get("confirmation_required")),
            },
            {
                "stage": "tool_executed",
                "executed": bool(entry.get("executed")),
                "actual_command": self._summarize_value(entry.get("actual_command", [])),
                "executor_user": self._summary(entry.get("executor_user", "")),
                "execution_success": bool(entry.get("execution_success")),
            },
            {
                "stage": "output_checked",
                "stdout_summary": self._summary(entry.get("stdout_summary", "")),
                "stderr_summary": self._summary(entry.get("stderr_summary", "")),
            },
            {
                "stage": "response_generated",
                "final_response": self._summary(entry.get("final_response", "")),
            },
            {
                "stage": "audit_saved",
                "summary": "Audit record prepared for durable storage.",
            },
        ])
        return {
            "request_id": self._summary(entry.get("request_id", "")),
            "session_id": self._summary(entry.get("session_id", "")),
            "original_request_id": self._summary(entry.get("original_request_id", "")),
            "events": events,
        }

    def _normalize_row(self, row: dict) -> dict:
        for key in ["tool_arguments", "execution_result", "rule_hits", "matched_rules", "actual_command"]:
            row[key] = self._json_loads(row.get(key), row.get(key))
        row["full_trace_json"] = self._json_loads(row.get("full_trace_json"), row.get("full_trace_json"))
        return row

    def _json_loads(self, value, default):
        if not value or not isinstance(value, str):
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    def _safe_json(self, value, limit: int = TEXT_LIMIT) -> str:
        try:
            encoded = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            encoded = json.dumps(str(value), ensure_ascii=False)
        return self._truncate(encoded, limit)

    def _truncate(self, value, limit: int = TEXT_LIMIT) -> str:
        text = "" if value is None else str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "...[truncated]"

    def _summary(self, value) -> str:
        return self._truncate(value, SUMMARY_LIMIT)

    def _summary_list(self, value) -> list:
        if not isinstance(value, list):
            value = [value] if value else []
        return [self._summary(item) for item in value[:20]]

    def _summarize_value(self, value):
        if isinstance(value, dict):
            return {self._summary(k): self._summary(v) for k, v in list(value.items())[:20]}
        if isinstance(value, list):
            return [self._summary(item) for item in value[:20]]
        return self._summary(value)


_logger = AuditLogger()


def get_logger() -> AuditLogger:
    return _logger
