"""文档里的数字必须与实测一致。

这个项目栽过一次：v1.3.0 后期新增 impact_analysis 工具、变更因果关联、
自学习基线监控与前门欺骗四项能力，但九份交付文档没有同步，工具数 16→17、
测试数 232→312、不变式 10→12 三组数字同时落后。评审看到自相矛盾的数字，
损失的是对全部数字的信任，不只是那三组。

所以不靠人记得改，改成：文档里凡是声明这些数字的地方，与
scripts/project_facts.py 的实测值不一致就构建失败，并指出文件与行号。

新增一类需要同步的数字时，往 CLAIM_PATTERNS 里加一条即可。
"""
import functools
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent


@functools.lru_cache(maxsize=1)
def _facts() -> dict:
    """惰性求值，绝不在模块级调用。

    project_facts.py 靠 `pytest --collect-only` 数用例，而收集会导入本模块。
    若在模块级就去取事实，就构成 pytest -> facts -> pytest 的无限递归。
    放进函数体后收集阶段不执行，环即断开；SAFEOPS_FACTS_CHILD 是第二道
    保险，万一将来有人把它挪回模块级，会得到明确报错而不是五分钟超时。
    """
    import json

    if os.environ.get("SAFEOPS_FACTS_CHILD"):
        pytest.skip("处于 project_facts 的子进程内，跳过以免递归")

    result = subprocess.run(
        [sys.executable, "scripts/project_facts.py", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, f"project_facts.py 失败:\n{result.stderr}"
    return json.loads(result.stdout)

# 每条规则：(可读名, 正则, 该匹配的实测事实键)。
# 正则的第一个捕获组是文档里写的数字。
CLAIM_PATTERNS = [
    ("受控工具数", re.compile(r"(\d+)\s*个受控(?:运维)?工具"), "tool_count"),
    ("受控工具数", re.compile(r"工具总数[^0-9]{0,8}(\d+)"), "tool_count"),
    ("自动化用例数", re.compile(r"(\d+)\s*项自动化(?:测试)?用例"), "test_collected"),
    ("自动化用例数", re.compile(r"(\d+)\s*tests? collected"), "test_collected"),
    ("安全不变式数", re.compile(r"(\d+)\s*条(?:安全)?不变式"), "invariant_count"),
    # "N 项安全对抗基准"指定义总数；执行数另有其名，见 benchmark_evaluated。
    # 早前这里错把执行数当成唯一口径，把本来准确的"64 项，63 执行，1 跳过"
    # 判成了过期，教训是：断言前先确认文档说的是哪个量。
    ("对抗基准定义数", re.compile(r"(\d+)\s*项安全对抗基准"), "benchmark_total"),
    ("对抗基准定义数", re.compile(r"安全基准\s*\|?\s*(\d+)\s*项"), "benchmark_total"),
    ("对抗基准执行数", re.compile(r"(\d+)\s*执行"), "benchmark_evaluated"),
    ("对抗基准跳过数", re.compile(r"(\d+)\s*跳过"), "benchmark_skipped"),
]

# "N passed, M skipped" 是一次运行的结果，不是项目属性：跳过数随平台与可选
# 依赖变化（同一提交在 Windows 跳 7 项、在 Linux 跳 6 项）。拿它当文档里的
# 门面数字，等于承诺一个换台机器就不成立的值。文档一律改用
# `pytest --collect-only` 的收集用例数，它与环境无关且可当场复核。
RUN_RESULT_PHRASING = re.compile(r"\d+\s*passed")

# 少数文档记录的是某次具体验证活动的历史结果，数字理应停在当时。
# 豁免必须写明理由，不接受空豁免。
HISTORICAL = {
    "docs/test-report.md": "记录某次真机验收的当时结果，是历史存档而非当前状态",
}


def _docs() -> list[Path]:
    paths = sorted((ROOT / "docs").glob("*.md"))
    paths.append(ROOT / "README.md")
    paths.extend([REPO / "README.md", REPO / "CHANGELOG.md"])
    return [p for p in paths if p.exists()]


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.relative_to(REPO).as_posix()


def _expected(key: str) -> int:
    return _facts()[key]


def test_documented_numbers_match_measured_reality():
    problems = []
    for path in _docs():
        rel = _rel(path)
        if rel in HISTORICAL:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for label, pattern, key in CLAIM_PATTERNS:
                for match in pattern.finditer(line):
                    claimed = int(match.group(1))
                    expected = _expected(key)
                    if claimed != expected:
                        problems.append(
                            f"{rel}:{lineno} {label} 写的是 {claimed}，实测 {expected}\n"
                            f"    > {line.strip()[:110]}"
                        )
    assert not problems, (
        "文档数字与实测不符（改文档，或先确认实测值确实变了）：\n\n"
        + "\n".join(problems)
    )


@pytest.mark.parametrize("rel,reason", sorted(HISTORICAL.items()))
def test_historical_exemptions_still_exist(rel, reason):
    """豁免清单不能悄悄指向已删除的文件，否则会变成沉默的漏网口。"""
    assert (ROOT / rel).exists(), f"豁免了不存在的文件: {rel}（理由: {reason}）"
    assert reason.strip(), f"{rel} 的豁免没有写理由"


def test_facts_script_reports_a_sane_project():
    """兜底：测量脚本本身坏掉时（比如注册表没加载）应当失败，而不是让
    所有文档断言因为 expected=0 而集体通过。"""
    facts = _facts()
    assert facts["tool_count"] > 0
    assert facts["test_collected"] > 0
    assert facts["invariant_count"] > 0
    assert facts["benchmark_total"] > 0
    assert facts["benchmark_evaluated"] > 0
    assert facts["benchmark_total"] == facts["benchmark_evaluated"] + facts["benchmark_skipped"]
    assert facts["readonly_tool_count"] + facts["confirm_tool_count"] == facts["tool_count"]


def test_docs_do_not_headline_a_run_result():
    """禁止用 "N passed" 当门面数字。

    跳过数随平台与可选依赖变化，同一提交在不同机器上得到不同的"正确值"。
    文档要写的是收集用例数（`pytest --collect-only`），环境无关、可当场复核。
    """
    offenders = []
    for path in _docs():
        rel = _rel(path)
        if rel in HISTORICAL:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if RUN_RESULT_PHRASING.search(line):
                offenders.append(f"{rel}:{lineno}  > {line.strip()[:110]}")
    assert not offenders, (
        "文档用了一次运行的结果当门面数字（跳过数随环境变化，换台机器就不成立）。\n"
        "请改成 `pytest --collect-only` 的收集用例数：\n\n" + "\n".join(offenders)
    )
