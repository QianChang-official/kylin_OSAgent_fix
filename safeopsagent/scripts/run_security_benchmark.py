#!/usr/bin/env python3
"""Run the SafeOpsAgent security benchmark and emit measured JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.security.benchmark import DEFAULT_CASES, run_security_benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = run_security_benchmark(args.cases)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
    return 0 if report["false_positive"] == 0 and report["false_negative"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
