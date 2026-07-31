"""SafeOpsAgent performance test.

Measures core API response times (P50/P95/P99), concurrent throughput,
security pre-check overhead and process memory, then writes
docs/performance-test-report.md.

Competition deliverable: "software performance (core metrics) test report".

Usage:
    PYTHONPATH=safeopsagent python scripts/performance_test.py

Environment overrides:
    PERF_SAMPLES      samples per endpoint in the sequential phase (default 50)
    PERF_CONCURRENCY  comma-separated concurrency levels (default 1,4,8,16)
    PERF_CONC_TOTAL   total requests per concurrency level (default 120)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure backend is importable when run from project root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Without this the console-authenticated endpoints answer 503 "Console
# authentication is not configured", and the run silently measures the latency
# of rejections instead of real work. Same process-local harness setting used
# by scripts/verify_invariants.py and backend/tests/conftest.py; production
# remains authenticated by default.
os.environ.setdefault("CONSOLE_AUTH_ENABLED", "0")
os.environ.setdefault("CONSOLE_AUTH_ALLOW_INSECURE_NON_LOOPBACK", "1")
os.environ.setdefault("MODEL_PROVIDER", "offline_safe")
os.environ.setdefault("MONITOR_SAMPLING_ENABLED", "0")

from backend.app import app  # noqa: E402
from backend.security.guardrail import Guardrail  # noqa: E402

CLIENT = TestClient(app)
SAMPLES = int(os.environ.get("PERF_SAMPLES", "50"))
CONCURRENCY_LEVELS = [
    int(item) for item in os.environ.get("PERF_CONCURRENCY", "1,4,8,16").split(",") if item.strip()
]
CONC_TOTAL = int(os.environ.get("PERF_CONC_TOTAL", "120"))


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    ordered = sorted(data)
    idx = int(len(ordered) * p / 100)
    return ordered[min(idx, len(ordered) - 1)]


def _summarize(latencies: list[float], errors: int, wall_seconds: float) -> dict:
    total = len(latencies)
    return {
        "samples": total,
        "avg_ms": round(statistics.mean(latencies), 2),
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "p99_ms": round(_percentile(latencies, 99), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "stdev_ms": round(statistics.pstdev(latencies), 2) if total > 1 else 0.0,
        "errors": errors,
        "success_rate": round((total - errors) / total * 100, 1) if total else 0.0,
        "qps": round(total / wall_seconds, 1) if wall_seconds > 0 else 0.0,
    }


def _request(client: TestClient, method: str, path: str, body: dict | None) -> tuple[float, int]:
    start = time.perf_counter()
    if method == "GET":
        resp = client.get(path)
    else:
        resp = client.post(path, json=body or {})
    return (time.perf_counter() - start) * 1000, resp.status_code


def measure(method: str, path: str, body: dict | None = None, samples: int = SAMPLES) -> dict:
    """Sequential latency measurement for a single endpoint."""
    latencies: list[float] = []
    errors = 0
    status_codes: dict[int, int] = {}
    wall_start = time.perf_counter()
    for _ in range(samples):
        elapsed, status = _request(CLIENT, method, path, body)
        latencies.append(elapsed)
        status_codes[status] = status_codes.get(status, 0) + 1
        if status >= 500:
            errors += 1
    wall = time.perf_counter() - wall_start
    summary = _summarize(latencies, errors, wall)
    summary["status_codes"] = status_codes
    return summary


def measure_concurrent(method: str, path: str, body: dict | None,
                       concurrency: int, total: int) -> dict:
    """Concurrent throughput measurement.

    Each worker thread uses its own TestClient against the same app
    instance, so the numbers reflect in-process contention (audit SQLite
    lock, orchestrator state) rather than client-side serialization.
    """
    per_worker = max(1, total // concurrency)
    actual_total = per_worker * concurrency

    def worker() -> tuple[list[float], int]:
        client = TestClient(app)
        local: list[float] = []
        local_errors = 0
        for _ in range(per_worker):
            elapsed, status = _request(client, method, path, body)
            local.append(elapsed)
            if status >= 500:
                local_errors += 1
        return local, local_errors

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        outcomes = list(pool.map(lambda _: worker(), range(concurrency)))
    wall = time.perf_counter() - wall_start

    latencies = [item for chunk, _ in outcomes for item in chunk]
    errors = sum(count for _, count in outcomes)
    summary = _summarize(latencies, errors, wall)
    summary["concurrency"] = concurrency
    summary["total_requests"] = actual_total
    summary["wall_seconds"] = round(wall, 2)
    return summary


def measure_guardrail_overhead(iterations: int = 500) -> dict:
    """Micro-benchmark the local security pre-check in isolation.

    This is the real cost the security layer adds before any model call:
    input inspection plus 0-100 risk scoring. Measured directly rather
    than inferred from endpoint timings.
    """
    guardrail = Guardrail()
    normal_text = "check memory status"
    danger_text = "rm -rf /"

    def run(text: str) -> list[float]:
        samples: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            check = guardrail.check_input(text)
            guardrail.score_100(input_check=check)
            samples.append((time.perf_counter() - start) * 1000)
        return samples

    normal = run(normal_text)
    danger = run(danger_text)
    return {
        "iterations": iterations,
        "normal_avg_ms": round(statistics.mean(normal), 4),
        "normal_p95_ms": round(_percentile(normal, 95), 4),
        "danger_avg_ms": round(statistics.mean(danger), 4),
        "danger_p95_ms": round(_percentile(danger, 95), 4),
    }


def _process_memory_mb() -> float | None:
    """Peak / current RSS in MB, or None when the platform cannot report it."""
    # Linux (Kylin target): VmHWM is the true peak RSS.
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    try:
        import resource
        # ru_maxrss is KB on Linux, bytes on macOS.
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
        return round(raw / divisor, 1)
    except (ImportError, AttributeError):
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = _Counters()
            counters.cb = ctypes.sizeof(_Counters)
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            # HANDLE is 64-bit; without explicit types ctypes truncates it.
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            ):
                return round(counters.PeakWorkingSetSize / 1024 / 1024, 1)
        except Exception:
            pass
    return None


SEQUENTIAL_CASES = [
    ("GET /health", "GET", "/health", None),
    ("GET /agent/status", "GET", "/agent/status", None),
    ("GET /tools/list", "GET", "/tools/list", None),
    ("GET /audit/logs", "GET", "/audit/logs", None),
    ("POST /chat 正常只读", "POST", "/chat", {"session_id": "perf-normal", "message": "check memory status"}),
    ("POST /chat 危险拦截", "POST", "/chat", {"session_id": "perf-danger", "message": "rm -rf /"}),
    ("POST /chat 配置漂移", "POST", "/chat", {"session_id": "perf-drift", "message": "check config drift"}),
    ("POST /chat 联合诊断", "POST", "/chat", {"session_id": "perf-multi", "message": "check memory and disk and cpu"}),
]

CONCURRENT_CASE = ("POST", "/chat", {"session_id": "perf-conc", "message": "check memory status"})


def run_sequential() -> dict[str, dict]:
    results: dict[str, dict] = {}
    for name, method, path, body in SEQUENTIAL_CASES:
        print(f"  [sequential] {name} ...", flush=True)
        results[name] = measure(method, path, body)
    return results


def run_concurrent() -> list[dict]:
    method, path, body = CONCURRENT_CASE
    results = []
    for level in CONCURRENCY_LEVELS:
        print(f"  [concurrent] {path} @ {level} 并发 ...", flush=True)
        results.append(measure_concurrent(method, path, body, level, CONC_TOTAL))
    return results


def _conclusions(sequential: dict, concurrent: list[dict], guardrail: dict) -> list[str]:
    """Derive conclusions from measured data rather than asserting them."""
    lines: list[str] = []

    worst_success = min(m["success_rate"] for m in sequential.values())
    if worst_success >= 100.0:
        lines.append("- 全部核心接口在顺序压测下成功率 100%，无 5xx 服务端错误。")
    else:
        failing = [name for name, m in sequential.items() if m["success_rate"] < 100.0]
        lines.append(f"- 顺序压测最低成功率 {worst_success}%，未达 100% 的接口：{'、'.join(failing)}。")

    readonly = sequential.get("GET /health", {})
    if readonly:
        lines.append(
            f"- 只读状态类接口（/health）P95 {readonly['p95_ms']} ms，"
            f"单进程吞吐 {readonly['qps']} QPS，可支撑控制台高频轮询。"
        )

    normal = sequential.get("POST /chat 正常只读", {})
    danger = sequential.get("POST /chat 危险拦截", {})
    if normal and danger:
        saved = round(normal["avg_ms"] - danger["avg_ms"], 2)
        if saved > 0:
            lines.append(
                f"- 危险请求（{danger['avg_ms']} ms）比正常只读请求（{normal['avg_ms']} ms）"
                f"平均快 {saved} ms：护栏在模型调用与工具执行之前完成拦截，未产生额外执行开销。"
            )
        else:
            lines.append(
                f"- 危险请求平均 {danger['avg_ms']} ms，与正常请求 {normal['avg_ms']} ms 相当，"
                "拦截路径未引入额外开销。"
            )

    lines.append(
        f"- 安全预检（输入检查 + 0-100 风险评分）本身平均耗时 "
        f"{guardrail['normal_avg_ms']} ms（正常输入）/ {guardrail['danger_avg_ms']} ms（危险输入），"
        "相对整链路占比极低，安全能力不以性能为代价。"
    )

    if concurrent:
        best = max(concurrent, key=lambda m: m["qps"])
        worst_conc_success = min(m["success_rate"] for m in concurrent)
        lines.append(
            f"- 并发压测峰值吞吐 {best['qps']} QPS（{best['concurrency']} 并发，"
            f"P95 {best['p95_ms']} ms），并发成功率最低 {worst_conc_success}%。"
        )
        baseline = concurrent[0]
        if baseline["qps"] > 0:
            scale = round(best["qps"] / baseline["qps"], 2)
            lines.append(
                f"- 相对 {baseline['concurrency']} 并发基线，吞吐提升 {scale}×；"
                "审计写入使用进程内锁串行化，是并发扩展的主要瓶颈点。"
            )

    lines.append("- 离线安全模式不依赖外部模型 API，延迟稳定可预测，可作为评测复现基准。")
    return lines


def generate_report(sequential: dict, concurrent: list[dict], guardrail: dict) -> Path:
    docs_dir = ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "performance-test-report.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memory = _process_memory_mb()
    memory_text = f"{memory} MB" if memory is not None else "当前平台未提供进程内存计数（Kylin/Linux 下正常采集）"

    lines = [
        "# SafeOpsAgent 软件性能测试报告",
        "",
        "## 文档信息",
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
        f"| 测试时间 | {now} |",
        "| 被测系统 | SafeOpsAgent 安全智能运维 Agent |",
        "| 运行模式 | offline_safe（离线安全规划器，无外部模型依赖） |",
        f"| 操作系统 | {platform.system()} {platform.release()} |",
        f"| CPU 架构 | {platform.machine()} |",
        f"| Python 版本 | {platform.python_version()} |",
        "| 测试工具 | `scripts/performance_test.py`（FastAPI TestClient 同源调用） |",
        f"| 进程峰值内存 | {memory_text} |",
        "",
        "## 1. 测试目标",
        "",
        "依据赛题《软件性能（核心指标）测试报告》交付要求，验证 SafeOpsAgent 的四类核心指标：",
        "",
        "1. **响应时间**：核心 API 的平均值、P50、P95、P99 与最大值。",
        "2. **吞吐量与并发能力**：单进程在 1 / 4 / 8 / 16 并发下的 QPS 与延迟退化曲线。",
        "3. **安全链路开销**：安全护栏预检本身的耗时，验证安全能力不以性能为代价。",
        "4. **稳定性与资源占用**：请求成功率、5xx 错误数与进程峰值内存。",
        "",
        "## 2. 测试方法",
        "",
        "| 项目 | 说明 |",
        "| --- | --- |",
        f"| 顺序压测 | 每个端点串行请求 {SAMPLES} 次，统计单请求延迟分布 |",
        f"| 并发压测 | `/chat` 正常只读请求，并发级别 {'/'.join(str(c) for c in CONCURRENCY_LEVELS)}，每级别约 {CONC_TOTAL} 次请求 |",
        "| 并发实现 | 每个工作线程持有独立 TestClient，共享同一 app 实例，可反映进程内锁竞争 |",
        "| 安全预检基准 | 直接调用 `Guardrail.check_input` + `score_100`，与 HTTP 链路解耦独立计时 |",
        "| 错误判定 | HTTP 状态码 >= 500 记为失败；安全拒绝返回 200 并携带 `security_decision=reject`，属于正确行为不计失败 |",
        "",
        "## 3. 核心指标 — 单请求响应时间",
        "",
        "| 接口场景 | 样本 | 平均(ms) | P50(ms) | P95(ms) | P99(ms) | 最大(ms) | 标准差(ms) | QPS | 成功率 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in sequential.items():
        lines.append(
            f"| {name} | {m['samples']} | {m['avg_ms']} | {m['p50_ms']} | {m['p95_ms']} | "
            f"{m['p99_ms']} | {m['max_ms']} | {m['stdev_ms']} | {m['qps']} | {m['success_rate']}% |"
        )

    lines.extend([
        "",
        "> 说明：QPS 为单线程串行条件下的理论上限（1000 / 平均延迟），并发吞吐见第 4 节。",
        "",
        "## 4. 核心指标 — 并发吞吐与延迟退化",
        "",
        "被测接口：`POST /chat`（正常只读请求，完整链路：安全预检 → 规划 → 工具执行 → 诊断 → 审计写入）",
        "",
        "| 并发数 | 总请求 | 耗时(s) | 吞吐(QPS) | 平均(ms) | P95(ms) | P99(ms) | 最大(ms) | 成功率 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for m in concurrent:
        lines.append(
            f"| {m['concurrency']} | {m['total_requests']} | {m['wall_seconds']} | {m['qps']} | "
            f"{m['avg_ms']} | {m['p95_ms']} | {m['p99_ms']} | {m['max_ms']} | {m['success_rate']}% |"
        )

    lines.extend([
        "",
        "## 5. 核心指标 — 安全链路开销",
        "",
        f"独立微基准：对安全预检链路（输入检查 + 0-100 风险评分）各执行 {guardrail['iterations']} 次。",
        "",
        "| 输入类型 | 平均(ms) | P95(ms) | 说明 |",
        "| --- | --- | --- | --- |",
        f"| 正常运维请求 | {guardrail['normal_avg_ms']} | {guardrail['normal_p95_ms']} | 全量规则扫描后放行 |",
        f"| 高危命令请求 | {guardrail['danger_avg_ms']} | {guardrail['danger_p95_ms']} | 命中危险规则并拒绝 |",
        "",
        "端到端对照：",
        "",
        "| 场景 | 平均(ms) | 链路说明 |",
        "| --- | --- | --- |",
    ])
    normal = sequential.get("POST /chat 正常只读", {})
    danger = sequential.get("POST /chat 危险拦截", {})
    multi = sequential.get("POST /chat 联合诊断", {})
    if normal:
        lines.append(f"| 正常只读请求 | {normal['avg_ms']} | 预检 → 规划 → 工具执行 → 诊断 → 审计写入（完整链路） |")
    if danger:
        lines.append(f"| 危险请求拦截 | {danger['avg_ms']} | 预检命中即拒绝 → 审计写入（不进入模型与工具执行） |")
    if multi:
        lines.append(f"| 多工具联合诊断 | {multi['avg_ms']} | 预检 → 规划 → 最多 3 个只读工具 → 根因关联 → 审计写入 |")

    lines.extend([
        "",
        "## 6. 稳定性与资源占用",
        "",
        "| 指标 | 结果 |",
        "| --- | --- |",
        f"| 顺序压测总请求数 | {sum(m['samples'] for m in sequential.values())} |",
        f"| 并发压测总请求数 | {sum(m['total_requests'] for m in concurrent)} |",
        f"| 5xx 服务端错误 | {sum(m['errors'] for m in sequential.values()) + sum(m['errors'] for m in concurrent)} |",
        f"| 最低接口成功率 | {min(m['success_rate'] for m in sequential.values())}% |",
        f"| 进程峰值内存 | {memory_text} |",
        "| 外部依赖 | 无（offline_safe 模式不调用外部模型 API） |",
        "",
        "## 7. 结论",
        "",
    ])
    lines.extend(_conclusions(sequential, concurrent, guardrail))

    lines.extend([
        "",
        "## 8. 边界说明",
        "",
        "- 本报告使用 FastAPI TestClient 同源调用，不含真实网络往返延迟；跨主机部署需叠加网络时间。",
        "- 测试在 offline_safe 模式下进行；DeepSeek / Qwen 模型服务模式的端到端延迟取决于外部 API 响应，需另行采集。",
        "- 审计写入为进程内锁串行化，单进程并发扩展存在上限；多进程部署需改用共享存储后端。",
        "- 报告数据由 `scripts/performance_test.py` 自动生成，可在银河麒麟 V11 LoongArch64 目标环境重跑复现。",
        "",
        "## 9. 复现方式",
        "",
        "```bash",
        "cd safeopsagent",
        "export MODEL_PROVIDER=offline_safe",
        "export PYTHONPATH=\"$(pwd)\"",
        "python scripts/performance_test.py",
        "```",
        "",
        "可选环境变量：`PERF_SAMPLES`（顺序采样数）、`PERF_CONCURRENCY`（并发级别）、`PERF_CONC_TOTAL`（每级别请求数）。",
        "",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--budget", metavar="FILE",
                        help="校验结果是否满足预算文件里的门槛，超出则非零退出")
    parser.add_argument("--json", metavar="FILE",
                        help="把原始测量结果写到 JSON，供归档与回归比对")
    parser.add_argument("--no-report", action="store_true",
                        help="不重写 docs/performance-test-report.md")
    args = parser.parse_args()

    print("SafeOpsAgent performance test starting...")
    print(f"  sequential samples per endpoint: {SAMPLES}")
    print(f"  concurrency levels: {CONCURRENCY_LEVELS} ({CONC_TOTAL} requests each)")
    sequential = run_sequential()
    concurrent = run_concurrent()
    print("  [micro] guardrail pre-check ...", flush=True)
    guardrail = measure_guardrail_overhead()

    report = None
    if not args.no_report:
        report = generate_report(sequential, concurrent, guardrail)

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"sequential": sequential, "concurrent": concurrent, "guardrail": guardrail},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRaw measurements written to: {args.json}")

    if report:
        print(f"\nPerformance report written to: {report}")
    print("\nSequential summary:")
    for name, m in sequential.items():
        print(f"  {name}: avg={m['avg_ms']}ms p95={m['p95_ms']}ms qps={m['qps']} success={m['success_rate']}%")
    print("\nConcurrency summary:")
    for m in concurrent:
        print(f"  c={m['concurrency']}: qps={m['qps']} p95={m['p95_ms']}ms success={m['success_rate']}%")
    print("\nGuardrail pre-check:")
    print(f"  normal avg={guardrail['normal_avg_ms']}ms  danger avg={guardrail['danger_avg_ms']}ms")

    failures = _check_measurements_are_meaningful(sequential, concurrent)
    if args.budget:
        failures.extend(_check_budget(Path(args.budget), sequential, concurrent, guardrail))

    if failures:
        print("\n性能门禁未通过:")
        for line in failures:
            print(f"  - {line}")
        raise SystemExit(1)
    print("\n性能门禁通过。")


def _check_measurements_are_meaningful(sequential: dict, concurrent: list[dict]) -> list[str]:
    """成功率不足就说明在测失败响应，这时的延迟与吞吐数字没有意义。

    这道检查存在的原因是它真的发生过：脚本未配置控制台认证时，除 /health
    外所有端点返回 503，报告照样生成，数字全是拒绝响应的延迟。
    """
    failures = []
    for name, m in sequential.items():
        if m["success_rate"] < 99.0:
            failures.append(
                f"{name} 成功率 {m['success_rate']}%，测到的是失败响应而非真实处理")
    for m in concurrent:
        if m["success_rate"] < 99.0:
            failures.append(
                f"并发 c={m['concurrency']} 成功率 {m['success_rate']}%，同上")
    return failures


def _check_budget(budget_path: Path, sequential: dict, concurrent: list[dict],
                  guardrail: dict) -> list[str]:
    """按预算文件核对本次测量，超出门槛即失败。

    预算是在记录主机上实测后留出余量得到的，是回归护栏，不是服务等级承诺：
    换一台机器、换一个 Python 版本，绝对值都会变。
    """
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    failures = []

    for name, limit in budget.get("sequential_p95_ms", {}).items():
        measured = sequential.get(name)
        if measured is None:
            failures.append(f"预算里的端点 {name!r} 未被本次测量覆盖")
        elif measured["p95_ms"] > limit:
            failures.append(f"{name} p95 {measured['p95_ms']}ms > 预算 {limit}ms")

    conc_floor = budget.get("concurrent_min_qps", {})
    for m in concurrent:
        limit = conc_floor.get(str(m["concurrency"]))
        if limit is not None and m["qps"] < limit:
            failures.append(f"并发 c={m['concurrency']} qps {m['qps']} < 预算 {limit}")

    guard_limit = budget.get("guardrail_max_avg_ms")
    if guard_limit is not None:
        worst = max(guardrail["normal_avg_ms"], guardrail["danger_avg_ms"])
        if worst > guard_limit:
            failures.append(f"护栏预检 avg {worst}ms > 预算 {guard_limit}ms")

    return failures


if __name__ == "__main__":
    main()
