"""Tamper-evidence primitives for the audit log.

Two properties are produced here, and they are deliberately kept separate
because they are not the same claim:

  Integrity     Each record commits to a digest of its own stored columns and
                to the digest of the record before it. Editing a column,
                deleting a record, reordering records, or dropping a whole
                day's table breaks the recomputation at a locatable position.

  Authenticity  When ``AUDIT_HMAC_KEY`` is configured, each link is also
                signed with HMAC-SHA256. Without the key an attacker who can
                write to the database can recompute a fully consistent chain;
                the signature is what makes that forgery infeasible.

The boundary is stated so it is not overread: this makes tampering
*detectable*, not *impossible*. An attacker holding the HMAC key, or one who
can suppress the writer before a record is committed, is outside what these
primitives can detect. Keeping the key off the audited host is what separates
"we can prove nobody edited this" from "we can prove nobody without the key
edited this".
"""
from __future__ import annotations

import hashlib
import hmac
import json

# 64 hex zeros. The prev_hash of the first record ever written.
GENESIS = "0" * 64

# Fixed column order. The digest is computed over these columns, in this
# order, so verification does not depend on SQLite row ordering or on the
# insertion dict's key order. Appending to this tuple is a breaking change to
# already-written chains and must go through a migration.
DIGEST_COLUMNS = (
    "timestamp",
    "session_id",
    "request_id",
    "user_input",
    "intent",
    "selected_tool",
    "tool_arguments",
    "risk_level",
    "confirmation_required",
    "executed",
    "execution_result",
    "final_response",
    "rule_hits",
    "duration_ms",
    "risk_score",
    "risk_level_text",
    "legacy_risk_level",
    "security_decision",
    "security_reason",
    "matched_rules",
    "actual_command",
    "executor_user",
    "execution_success",
    "stdout_summary",
    "stderr_summary",
    "full_trace_json",
)


def canonical_payload(values: dict) -> str:
    """Serialize the digest columns deterministically.

    Values are coerced to ``str`` before hashing. SQLite type affinity means
    an INTEGER column can read back as ``int`` on one path and ``str`` on
    another; coercing removes that ambiguity so a record written today
    verifies identically when read back tomorrow. ``None`` and missing map to
    the same empty string, matching how the writer stores absent fields.
    """
    ordered = [[column, "" if values.get(column) is None else str(values.get(column))]
               for column in DIGEST_COLUMNS]
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


def payload_digest(values: dict) -> str:
    return hashlib.sha256(canonical_payload(values).encode("utf-8")).hexdigest()


def link(prev_hash: str, digest: str) -> str:
    """Chain one record to its predecessor."""
    return hashlib.sha256(f"{prev_hash}:{digest}".encode()).hexdigest()


def sign(entry_hash: str, key: bytes | None) -> str:
    """Sign a link. Returns "" when no key is configured."""
    if not key:
        return ""
    return hmac.new(key, entry_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def signature_matches(entry_hash: str, signature: str, key: bytes | None) -> bool:
    """Constant-time signature check."""
    if not key:
        return False
    return hmac.compare_digest(sign(entry_hash, key), signature or "")
