# ADR-0004：文档数字以实测为唯一来源，不一致即构建失败

状态：已采纳 · 2026-08-01

## 背景

v1.3.0 后期新增了影响面预测工具、变更—故障因果关联、自学习基线监控与前门欺骗
四项能力。工具数 16→17、自动化用例数、不变式数 10→13 三组数字随之变化，但九份
交付文档没有同步：

- `final-delivery-checklist.md`、`compatibility-matrix.md`、`final-validation-slide.md`
  仍写 232 项测试、16 个工具
- `functional-design.md`、`product-manual.md`、`presentation-outline.md`、
  `requirements-analysis.md` 仍写 16 个工具
- `innovation-highlights.md`、`presentation-outline.md` 仍写 10 条不变式
- README 自身也落后

评审看到互相矛盾的数字，损失的不只是那三组数字的可信度，而是对**全部**数字的
信任。这个损失远大于数字本身的偏差。

## 决策

**数字只有一个来源：`scripts/project_facts.py` 的实测输出。**
文档里凡是声明这些数字的地方，与实测不一致即让构建失败，并指出文件与行号
（`backend/tests/test_docs_consistency.py`）。

新增一类需要同步的数字，往 `CLAIM_PATTERNS` 加一条正则即可。

## 两个在实施中学到的教训

**一、不要拿"一次运行的结果"当文档数字。**
最初用 `N passed, M skipped` 做基准，但跳过数随平台与可选依赖变化——同一提交在
Windows 跳 7 项、Linux 跳 6 项。作为门禁基准它必然在某个平台误报。改用
`pytest --collect-only` 的收集用例数：环境无关，任何人可当场复核。为此还加了一条
测试，禁止文档再用 `N passed` 当门面数字。

**二、断言之前先确认文档说的是哪个量。**
门禁第一版把"64 项安全对抗基准"判为过期，理由是实测 `evaluated_cases` 是 63。
但基准实际定义 64 条、执行 63 条、跳过 1 条——文档写的"64 项，63 执行，1 跳过"
完全准确，错的是门禁把执行数当成了唯一口径。修正后 `project_facts.py` 同时报告
`benchmark_total` 与 `benchmark_evaluated`，两个量分别断言。

一道会误报的门禁比没有门禁更糟：它会训练人去无视告警。

## 后果

- 改代码导致这些数字变化时，必须同步改文档，否则 PR 变红。这是有意的摩擦。
- `docs/test-report.md` 记录的是某次真机验收的当时结果，属历史存档，在
  `HISTORICAL` 里显式豁免并写明理由。豁免必须带理由，且有测试防止豁免指向
  已删除的文件而变成沉默的漏网口。
- 兜底断言 `test_facts_script_reports_a_sane_project` 防止测量脚本自身坏掉时
  （例如工具注册表未加载导致 `tool_count=0`）所有文档断言因期望值为 0 而集体
  通过——这个坑在开发过程中真的踩到过。
