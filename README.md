# kylin_OSAgent_fix

[![CI](https://github.com/QianChang-official/kylin_OSAgent_fix/actions/workflows/ci.yml/badge.svg)](https://github.com/QianChang-official/kylin_OSAgent_fix/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-2ea44f.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)

面向银河麒麟操作系统的安全智能运维 Agent —— 第十五届中国软件杯 A 组赛题作品仓库。

出题企业：麒麟软件有限公司
目标环境：银河麒麟高级服务器版 V11 (Swan25) / LoongArch64

## 核心性质

| 性质 | 实现 | 证据 |
| --- | --- | --- |
| 模型不能直接执行系统命令 | SafeExecutor 单点收口，禁止 `shell=True` | INV-S1..INV-S5 AST 静态检查（CI 阻断） |
| 高危输入在调用模型前被拦截 | Guardrail 本地预检，拦截不进入模型上下文 | INV-R3，安全对抗基准 64 用例 FP=0 FN=0 |
| 审计记录防篡改，改写与删除可检测 | SHA-256 哈希链 + 可选 HMAC 签名 | `test_audit_chain.py`，离线验证器可独立核对 |
| 审计不可写时拒绝执行（fail-closed） | preflight() 在工具执行前检查 | `test_audit_gate_entry_points.py` |
| 所有保证与实现一致、数字与代码同步 | `scripts/project_facts.py` 实测，CI 比对文档声明 | `test_docs_consistency.py`（不一致即构建失败）|

## 仓库结构

```
safeopsagent/          项目主体（后端、前端、脚本、交付文档）
  docs/adr/            架构决策记录：审计防篡改 / 执行范围 / 集成面 / 数字来源
  backend/             FastAPI 后端，17 个受控运维工具，全链路安全护栏
  frontend/vue-console Vue 可视化控制台
  scripts/             不变式门禁、安全基准、性能测试、离线审计验证器
```

项目说明、部署方式与全部交付文档见 [`safeopsagent/README.md`](safeopsagent/README.md)。

## 快速开始

```bash
cd safeopsagent
python3 -m pip install -r backend/requirements-kylin.txt
export MODEL_PROVIDER=offline_safe
export PYTHONPATH="$(pwd)"
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000/console/`。

验证安全不变式与对抗基准（无需外网/API Key）：

```bash
python scripts/verify_invariants.py   # 13 条不变式，失败非零退出
python scripts/run_security_benchmark.py  # 64 用例，FP/FN 回归阻断
python scripts/verify_audit_chain.py --db data/audit.db  # 离线审计核验
```

