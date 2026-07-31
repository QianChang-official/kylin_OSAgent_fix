# SafeOpsAgent 最终交付检查清单

本文档用于提交前人工核对，确保代码、文档、演示和打包材料一致。

## 1. Git 基线

```bash
git branch --show-current
git rev-parse --short HEAD
git status --short
```

当前最终材料同步基线：

```text
branch: dev
tag: safeopsagent-v1.3.0-final-delivery
package: safeopsagent-<tag-commit-short-hash>-final-delivery.tar.gz
SHA256: read from the adjacent package .sha256 file
```

要求：

- 完成全部验收后只新建 `safeopsagent-v1.3.0-final-delivery`；任何旧标签都不得移动。
- 不提交 `.venv`、`.venv-frontend`、`node_modules`、`__pycache__`、`.pytest_cache`、运行时 `data/` 或 `audit.db`。
- v1.3.0 新增跨工具根因分析引擎、配置漂移/僵尸进程/磁盘 I/O 三个场景工具、MCP SSE 传输，并补齐全部交付文档。

## 2. 后端验证

```bash
python -c "import backend.app; print('import-ok')"
python -m pytest -q
```

本地最终候选结果：

```text
import-ok: pass
pytest: 434 项用例收集并通过（跳过项随环境变化）
security benchmark: 64 cases, 63 evaluated, 1 skipped, false_positive=0, false_negative=0
```

官方 Kylin V11 LoongArch64 v1.2 RC 复验结果：

```text
import-ok: pass
pytest: 通过
```

官方环境：

```text
OS: Kylin Linux Advanced Server V11 (Swan25)
Arch: loongarch64
Kernel: 6.6.0-32.7.v2505.ky11.loongarch64
Python: 3.11.6
```

## 3. 静态安全检查

```bash
rg -n "shell=True" backend
rg -n "subprocess\.run" backend
```

要求：

- `shell=True` 无结果。
- `subprocess.run` 只出现在 `backend/executor/safe_executor.py`。

API Key 检查：

```bash
rg -n "sk-[A-Za-z0-9]|api_key\s*=\s*['\"][^'\"]+|MODEL_API_KEY=.*[A-Za-z0-9]{16,}" backend frontend tests docs README.md .env.example
```

要求：

- 不出现真实 API Key。
- 文档只使用 `<your-api-key>` 或空值占位。

## 4. Vue 控制台验证

Vue 控制台已经合入 `dev`，由 FastAPI 同源托管，运行时不依赖 Node、Streamlit 或 pyarrow。

部署要求：

- 默认只启用 `safeops-agent.service`。
- Kylin 主入口为 `/console/`。
- `safeops-web.service` 仅作为可选 Streamlit 开发/备用服务，不默认启用。

官方 Kylin 复验路由：

```text
/console/
/console/diagnosis
/console/security
/console/tools
/console/audit
```

要求：

- 以上路由均返回 200。
- SPA fallback 只作用于 `/console/`，不吞掉 `/health`、`/chat`、`/tools/*`、`/audit/*`、`/system/probe`。
- 页面不展示 API Key、内部异常堆栈或敏感配置。
- 危险请求明确展示“已阻断、未执行”。

说明：官方复验中浏览器转发曾出现 reset，但 Kylin 本机 `curl` 与龙芯浏览器 headless 截图已验证 `/console/`。

## 5. 模型服务验证

离线安全模式：

```bash
export MODEL_PROVIDER=offline_safe
```

DeepSeek 受控联调：

```bash
export MODEL_PROVIDER=deepseek
export MODEL_API_BASE=https://api.deepseek.com
export MODEL_API_KEY=<your-api-key>
export MODEL_NAME=deepseek-chat
```

DeepSeek 联调已验证：

- `agent_mode=model_api`
- `model_provider=deepseek`
- `model_vendor=DeepSeek`
- `model_name=deepseek-chat`
- `planner_source=domestic_model`
- `check memory status` 成功规划 `get_memory_status`
- `rm -rf /`、Prompt Injection、`/etc/shadow` 均在模型调用前拒绝
- API 响应、Audit Trace、Uvicorn log 均未泄漏 Key

要求：

- API Key 只通过当前 shell 环境变量注入。
- 不写入 `.env`、配置文件、日志、截图或审计。
- 联调结束后清理环境变量。

## 6. 演示主线检查

必须能演示：

1. 工作台显示 Agent 在线状态、运行模式、模型提供方和安全链路。
2. 正常只读请求：`check memory status`。
3. 工具规划：展示 `tool_plan` 和只读工具执行状态。
4. 危险请求：`rm -rf /` 返回 `risk_score=100`、`reject`、未执行。
5. Prompt Injection：输出 system prompt / 不记录日志被拒绝并写审计。
6. 受保护路径：`/etc/shadow` 请求被拒绝。
7. 审计回放：通过 `request_id` 查询 `/audit/trace/{request_id}`。
8. 工具能力：说明白名单、参数校验、只读边界和审计记录。

## 7. Kylin / LoongArch64 证据材料

建议准备截图或文本证据：

- `uname -a`
- `uname -m`
- `/etc/os-release`
- `python3 --version`
- `python -m pytest -q`
- `python -c "import backend.app; print('import-ok')"`
- `rg -n "shell=True" backend`
- `rg -n "subprocess\.run" backend`
- `/agent/status`
- `/chat` 正常只读请求
- `rm -rf /` 拒绝
- Prompt Injection 拒绝
- `/etc/shadow` 拒绝
- `/audit/logs`
- `/audit/trace/{request_id}`
- `/console/` 及四个子路由返回 200

## 8. 打包检查

生成交付包：

```bash
python scripts/package-final.py
```

默认输出文件名为 `../safeopsagent-<commit>-final-delivery.tar.gz`，其中 `<commit>` 为当前 Git 短 hash。最终 SHA256 写入包旁同名校验文件，不回写源码包：

```text
safeopsagent-<commit>-final-delivery.tar.gz
safeopsagent-<commit>-final-delivery.tar.gz.sha256
```

检查顶层目录：

```bash
tar -tzf ../safeopsagent-<commit>-final-delivery.tar.gz | head
```

要求包内顶层目录为：

```text
safeopsagent/
```

必须排除：

- `.git`
- `.env`
- `*.key`
- `*.pem`
- `.venv`
- `.venv-frontend`
- `node_modules`
- `__pycache__`
- `.pytest_cache`
- 运行时 `data/`
- `audit.db`

保留：

- README
- docs
- backend
- frontend
- Vue 构建产物 `backend/static/console`
- scripts
- deploy
- tests/data 测试 fixture

## 9. 文档一致性检查

### 9.1 口径准确性

检查文档中的以下表述是否与实测一致：

| 事实项 | 正确口径 |
| --- | --- |
| 工具数量 | 17 个受控工具：15 个自动只读/安全规划，2 个需人工确认 |
| 自动化测试 | 434 项自动化用例（跳过项须逐条说明原因，不计为通过） |
| 安全基准 | 64 项，63 执行，1 跳过，误报 0，漏报 0 |
| MCP 传输 | stdio 与 SSE / Streamable HTTP 双传输，SDK 为可选依赖 |
| 版本号 | v1.3.0（README、app.py、mcp_server.py、package.json 四处一致） |
| 麒麟复验 | 基线 `57d90f8` 已验证核心闭环；v1.3.0 新增能力建议目标机补跑回归 |

### 9.2 不得出现的表述

- 不把项目称为"比赛级 MVP"或"不是生产级平台"。
- 不声明 openGauss、本地大模型、ModelHub、RAG 已完成。
- 不声明多租户、RBAC 权限体系已完成。
- 不声明自动删除、自动重启、自动修复或自愈已完成。
- 不声明真实 API Key 写入配置文件。
- 不声明 Streamlit 是官方 Kylin 主展示入口。
- 不声明 MCP SDK 已在官方 Kylin 完整实测。
- 不把测试跳过项笼统计为"全部通过"。

### 9.3 能力边界的表述方式

能力边界应表述为**设计选择**并给出理由，而不是表述为未完成项：

```text
✅ 不提供永久删除：不可逆操作违背安全可控原则，只提供可恢复隔离。
❌ 永久删除功能未纳入当前 MVP。
```

需要按此方式表述的边界：永久删除、自动重启/自愈、内核修改、多租户 RBAC、本地大模型/RAG、openGauss。

已知工程约束（据实说明，不粉饰）：

- 审计写入为进程内锁串行化，单进程并发吞吐存在上限。
- Session 与 confirmation token 保存在进程内存，多进程部署需共享状态。
- 长期压测、HA 与集群部署未纳入当前验证范围。

## 10. 最终提交前确认

提交前确认：

- 代码和文档没有真实 API Key。
- 安全主链路没有绕过 SafeExecutor。
- 交付包不包含运行时数据库和虚拟环境。
- README 能说明项目定位、启动方式、演示路径、验证事实和边界。
- 演示脚本能覆盖正常请求、危险拦截、Prompt Injection、审计回放和 Vue 控制台。
