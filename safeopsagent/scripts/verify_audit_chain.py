#!/usr/bin/env python3
"""Offline verifier for the SafeOpsAgent audit hash chain.

Recomputes every record's digest and its link to the previous record, and
reports where the chain first breaks. Runs against a database file alone --
no running backend, no network -- so an auditor can check history on a copy
of the file.

What a clean result does and does not prove:

  integrity_ok=true    No record was modified, deleted, reordered, and no
                       daily table was dropped, *by anyone who could not
                       recompute the chain*.

  authenticity         "verified" only when AUDIT_HMAC_KEY is supplied and
                       every link's signature matches. "unsigned" means no
                       key was configured when the records were written: a
                       writer with database access could have rebuilt a
                       consistent chain, and this tool cannot tell.

Exit codes: 0 verified, 1 broken, 2 usage/IO error.

Usage:
    python scripts/verify_audit_chain.py
    python scripts/verify_audit_chain.py --db data/audit.db --json
    AUDIT_HMAC_KEY=... python scripts/verify_audit_chain.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402
from backend.audit.logger import AuditLogger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=None,
                        help="audit database path (default: configured AUDIT_DB_PATH)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else config.AUDIT_DB_PATH
    if not db_path.exists():
        print(f"audit database not found: {db_path}", file=sys.stderr)
        return 2

    try:
        report = AuditLogger(db_path).verify_chain()
    except Exception as exc:  # unreadable / not a database
        print(f"cannot read audit database: {exc}", file=sys.stderr)
        return 2

    report["database"] = str(db_path)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["integrity_ok"] else 1

    print(f"database        {db_path}")
    print(f"records         {report['records']} "
          f"(chained {report['chained']}, pre-migration {report['unchained_legacy']})")
    print(f"integrity       {'OK' if report['integrity_ok'] else 'BROKEN'}")
    print(f"authenticity    {report['authenticity']}")
    if report["first_break"]:
        brk = report["first_break"]
        print()
        print("first break")
        print(f"  reason        {brk['reason']}")
        print(f"  table         {brk['table']}")
        print(f"  row id        {brk['id']}")
        print(f"  request_id    {brk['request_id']}")
    if report["authenticity"] in {"unsigned", "no_key"}:
        print()
        print("note: " + report["boundary"])
    return 0 if report["integrity_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
