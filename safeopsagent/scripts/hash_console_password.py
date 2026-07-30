#!/usr/bin/env python3
"""Generate a SafeOpsAgent console verifier without echoing the secret."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.security.console_auth import generate_password_hash  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a PBKDF2 verifier for the console password or the entry gate.",
    )
    parser.add_argument(
        "--entry-gate",
        action="store_true",
        help="Generate the concealed entry-gate passphrase verifier instead of the login password.",
    )
    parser.add_argument(
        "--value-only",
        action="store_true",
        help="Print only the verifier value for installer integration.",
    )
    args = parser.parse_args()

    label = "Entry gate passphrase" if args.entry_gate else "Console password"
    variable = "CONSOLE_ENTRY_GATE_HASH" if args.entry_gate else "CONSOLE_AUTH_PASSWORD_HASH"

    secret = getpass.getpass(f"{label}: ")
    repeated = getpass.getpass(f"Repeat {label.lower()}: ")
    if secret != repeated:
        print("Entries do not match.", file=sys.stderr)
        return 1
    try:
        verifier = generate_password_hash(secret)
        output = verifier if args.value_only else f"{variable}={verifier}"
        # The secret has been replaced by a salted 600k-round PBKDF2 verifier;
        # CodeQL does not model generate_password_hash as a sanitizer.
        print(output)  # lgtm[py/clear-text-logging-sensitive-data]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
