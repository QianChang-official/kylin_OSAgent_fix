#!/usr/bin/env python3
"""Generate a SafeOpsAgent console password hash without echoing the password."""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.security.console_auth import generate_password_hash  # noqa: E402


def main() -> int:
    password = getpass.getpass("Console password: ")
    repeated = getpass.getpass("Repeat password: ")
    if password != repeated:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        print(generate_password_hash(password))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
