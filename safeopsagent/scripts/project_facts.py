#!/usr/bin/env python3
"""测量项目的可核对事实，作为文档数字的唯一来源。

存在的理由：工具数 16→17、测试数 232→312→423、不变式 10→12→13 这几组数字
散落在十几份文档里，每次新增能力都要人工同步，实际结果是九份交付文档同时
落后。与其靠人记得改，不如让文档里的数字与本脚本的测量值不一致时直接构建
失败（见 backend/tests/test_docs_consistency.py）。

用法：
    python scripts/project_facts.py            # 人读
    python scripts/project_facts.py --json     # 机读
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CONSOLE_AUTH_ENABLED", "0")
os.environ.setdefault("CONSOLE_AUTH_ALLOW_INSECURE_NON_LOOPBACK", "1")
os.environ.setdefault("MODEL_PROVIDER", "offline_safe")
os.environ.setdefault("MONITOR_SAMPLING_ENABLED", "0")


def collect() -> dict:
    import backend
    import backend.app
    from backend.agent.orchestrator import CHAT_READONLY_TOOLS
    from backend.security.invariants import STATIC_INVARIANTS
    from backend.tools.registry import get_registry

    tools = get_registry().list_tools()

    runtime_src = (ROOT / "scripts" / "verify_invariants.py").read_text(encoding="utf-8")
    block = re.search(r"RUNTIME_INVARIANTS = \{(.*?)\n\}", runtime_src, re.S)
    runtime_ids = re.findall(r'"(INV-R\d+)"', block.group(1)) if block else []

    facts = {
        "version": backend.__version__,
        "tool_count": len(tools),
        "readonly_tool_count": len(CHAT_READONLY_TOOLS),
        "confirm_tool_count": len(tools) - len(CHAT_READONLY_TOOLS),
        "static_invariant_count": len(STATIC_INVARIANTS),
        "runtime_invariant_count": len(runtime_ids),
        "invariant_count": len(STATIC_INVARIANTS) + len(runtime_ids),
    }
    facts.update(_measure_tests())
    facts.update(_measure_benchmark())
    return facts


def _measure_tests() -> dict:
    """收集测试数量。用子进程跑，避免把 pytest 的收集状态带进当前解释器。"""
    result = subprocess.run(
        # -o addopts= 清空 pyproject 里的 -q：两个 -q 会让 pytest 只打印
        # 每个文件的条数而不打印总数，正则就匹配不到了。
        [sys.executable, "-m", "pytest", "-o", "addopts=", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
        env={**os.environ, "SAFEOPS_FACTS_CHILD": "1"},
    )
    collected = re.search(r"(\d+) tests? collected", result.stdout)
    return {"test_collected": int(collected.group(1)) if collected else 0}


def _measure_benchmark() -> dict:
    from backend.security.benchmark import run_security_benchmark

    report = run_security_benchmark()
    # 定义数与执行数不是一回事：基准定义 N 条，其中若干条因环境不满足被跳过。
    # 文档里"N 项安全对抗基准"指的是定义总数，"N 执行"指实际评测数，
    # 两个都要给，否则读者无从判断某个数字说的是哪一个。
    return {
        "benchmark_total": report["total_cases"],
        "benchmark_evaluated": report["evaluated_cases"],
        "benchmark_skipped": report["skipped_cases"],
        "benchmark_false_positive": report["false_positive"],
        "benchmark_false_negative": report["false_negative"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    facts = collect()
    if args.json:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
    else:
        width = max(len(k) for k in facts)
        for key, value in facts.items():
            print(f"  {key.ljust(width)} : {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
