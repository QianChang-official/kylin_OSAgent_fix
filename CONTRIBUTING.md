# 贡献指南

## 环境

```bash
cd safeopsagent
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

Python 3.11 是麒麟 V11 的目标版本，CI 同时跑 3.12 以防止漂移。

## 跑起来

```bash
cd safeopsagent

# 测试。pyproject 已配好 pythonpath，不需要手动导出 PYTHONPATH
MODEL_PROVIDER=offline_safe MONITOR_SAMPLING_ENABLED=0 python -m pytest

# 安全不变式（静态 AST + 运行时行为），失败非零退出
MODEL_PROVIDER=offline_safe python scripts/verify_invariants.py

# 安全对抗基准，误报或漏报非零即视为回归
MODEL_PROVIDER=offline_safe python scripts/run_security_benchmark.py

# 审计链离线核验
python scripts/verify_audit_chain.py --db data/audit.db
```

`MODEL_PROVIDER=offline_safe` 让全部本地验证在无外网、无 API Key 时可完整运行。
**不要为了跑测试去配真实模型密钥。**

## 提交前必须通过的门禁

CI 会跑这四类检查，本地先过一遍能省一轮往返：

| 门禁 | 命令 | 失败意味着 |
| --- | --- | --- |
| 测试 | `python -m pytest` | 功能回归 |
| 安全不变式 | `python scripts/verify_invariants.py` | 护栏的结构性或行为性保证被破坏 |
| 对抗基准 | `python scripts/run_security_benchmark.py` | 误报或漏报回归 |
| 控制台产物一致 | 见 `.github/workflows/ci.yml` | 改了控制台源码但没提交重新构建的产物 |

控制台由后端同源托管在 `backend/static/console/`，**构建产物是提交进仓库的**。
改了 `frontend/vue-console/src/` 就必须 `npm run build` 并把产物一起提交，否则
线上跑的是旧界面。CI 里那条检查专门防这个，并且刻意排在 build 之前——先 build
再检查会让断言恒真。

## 写变更的规矩

这个项目的核心资产是"声明与实现一致"。请遵守：

1. **每条对外保证都要能指到一条回归测试。** 新增能力时，README 或 CHANGELOG 里
   写下的每句保证，都应该有对应测试。指不到测试的句子，不要写。

2. **主动写明边界。** 说清楚一个机制**不能**证明什么，和说清楚它能证明什么同样
   重要。例如审计链在无 `AUDIT_HMAC_KEY` 时不具备真实性，这一点不仅写进了
   `SECURITY.md`，还有一条专门的测试
   （`test_the_same_forgery_is_invisible_without_a_key`）把它钉死，防止后来的人
   把文档改得比实现更强。

3. **不要把计划中的能力写成已完成。** 状态表里的"已完成"意味着有测试覆盖。

4. **改动要能追溯到需求。** 不顺手"改进"相邻代码、注释或格式。发现无关的死代码，
   在 PR 里提出来，不要直接删。

## 版本号

唯一来源是 `safeopsagent/backend/__init__.py` 的 `__version__`。
`backend.app.APP_VERSION`、`pyproject.toml` 的 dynamic version、
`scripts/package-final.py` 全部由它派生。改一处即可，
`test_packaging_metadata.py` 会验证没有第二个来源冒出来。

依赖同理：运行时依赖只写在 `backend/requirements.txt`，`pyproject.toml` 动态读取
它，不要在两个地方各列一份。

## 代码风格

`ruff` 配置在 `safeopsagent/pyproject.toml`。规则集从真实缺陷（`E`/`F`/`B`）、
导入顺序（`I`）与现代化（`UP`）起步，纯风格类规则不进门禁——避免为了过 lint 去
改动与本次工作无关的历史代码。

```bash
cd safeopsagent
python -m ruff check .
python -m ruff check . --fix
```

## 安全问题

不要开公开 issue，走 GitHub private vulnerability reporting，见 `SECURITY.md`。
