# SafeOpsAgent

SafeOpsAgent 是面向银河麒麟操作系统的安全智能运维 Agent。项目的核心目标不是把大模型变成开放 Shell，而是在自然语言和操作系统之间增加一层安全控制面：**模型负责理解、规划和总结，系统负责安全预检、工具白名单、风险评分、最小权限执行和审计追踪。模型永远不能直接执行系统命令。**

当前版本 v1.3.0 提供完整的安全智能运维能力：17 个受控运维工具、跨工具根因分析引擎、变更—故障因果关联、操作影响面预测、自学习基线监控大盘、五层安全护栏、MCP 双传输协议、Vue 可视化控制台与全链路审计追踪。系统已在银河麒麟 V11 LoongArch64 环境完成真机复验，312 项自动化测试通过，64 项安全对抗基准误报 0、漏报 0，10 条安全不变式机器验证全部成立。

## 核心能力

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| Guardrail 安全护栏 | 已完成 | 在模型调用前拦截危险命令、Prompt Injection、审计绕过和受保护路径访问。 |
| RiskScorer 风险量化 | 已完成 | 输出 0-100 `risk_score`、`risk_level`、`security_decision` 和规则命中。 |
| SafeExecutor 最小权限执行 | 已完成 | 所有系统命令统一通过最小权限执行代理，禁止 `shell=True`，全后端单点收口。 |
| 国产模型适配层 | 已完成 | 支持 `deepseek`、`qwen`、`kimi`、`custom`、`offline_safe`，模型只做意图理解和工具规划。 |
| 离线安全规划器 | 已完成 | 无外网、无 API Key 时仍可完成完整安全运维闭环。 |
| Tool Registry | 已完成 | 17 个受控工具：9 个基础感知 + 3 个场景专项 + 1 个影响面预测 + 2 个清理扫描/计划 + 2 个需确认处置。 |
| **跨工具根因分析** | 已完成 | 5 个探测器关联多工具证据，输出带置信度的根因链与安全评估。 |
| **关键文件保护** | 已完成 | 自动识别数据库文件并排除清理；归属未知的文件默认保护（fail-safe）。 |
| **配置漂移检测** | 已完成 | 关键配置指纹基线对比，识别内容/权限/属主变更，敏感配置定级 critical。 |
| **僵尸进程检测** | 已完成 | 检测 Z 状态进程、定位父进程，区分 init 自动 reap 与服务未回收。 |
| **磁盘 I/O 分析** | 已完成 | 解析 `iostat -x`，按利用率与响应延迟双阈值识别瓶颈设备。 |
| **变更—故障因果关联** | 已完成 | 持久化配置漂移时间线，按实体与时间双轴对齐，定位"是哪次变更导致的故障"。 |
| **操作影响面预测** | 已完成 | 处置前推演持有进程、所属服务与监听端口，识别句柄泄漏陷阱并给出 truncate/rm 建议。 |
| **自学习基线监控** | 已完成 | 中位数 + MAD 从本机历史学习正常区间，替代固定阈值；含监控大盘与偏离告警。 |
| **安全不变式自证明** | 已完成 | 5 条静态 + 5 条运行时不变式机器验证，输出验证报告，失败非零退出可作发布门禁。 |
| `/chat` Agent 编排 | 已完成 | 支持最多 3 个只读工具联合诊断，返回由真实工具数据生成的诊断、证据、根因链和建议。 |
| 可恢复安全清理 | 已完成 | 仅在临时目录白名单中扫描和计划；隔离/恢复需 dry-run、一次性确认、元数据复验和审计，不永久删除。 |
| `/tools/call` / `/tools/confirm` | 已完成 | 支持 allow / confirm / reject 三态决策，中风险 dry-run 后人工确认。 |
| Audit Trace v2 | 已完成 | 每次请求生成 `request_id`，可回放安全检查、工具规划、执行和审计事件；append-only 不可清除。 |
| Session TTL | 已完成 | 限制会话生命周期和最大消息数，避免上下文无限增长。 |
| Vue 控制台 | 已完成 | FastAPI 同源托管 `/console/`，运行时不依赖 Node、Streamlit 或 pyarrow。 |
| **MCP stdio + SSE** | 已完成 | 17 个工具以 MCP 标准协议暴露，支持 stdio 与 SSE / Streamable HTTP 双传输，同源同端口。 |
| Streamlit 备用前端 | 保留 | 可用于开发演示，不是 Kylin LoongArch64 主展示路径。 |

## 安全链路

```text
自然语言请求
  -> Guardrail 本地安全预检        ← 危险请求在此拦截，不进入模型
  -> 国产模型服务 / 离线安全规划器
  -> tool_plan 工具规划
  -> Tool Registry 白名单与参数校验
  -> RiskScorer 风险评分（allow / confirm / reject）
  -> SafeExecutor 只读工具执行
  -> 工具输出安全复检
  -> 跨工具根因分析
  -> Audit Trace 审计回放
```

关键边界：

- 模型不能直接执行系统命令。
- 高风险请求在模型调用或工具执行前被拒绝。
- 自动执行范围仅限只读运维工具以及不会修改文件的清理扫描/计划。
- 中风险工具调用需要 dry-run 和一次性令牌人工确认。
- 每次允许、拒绝或环境受限请求都会写入审计，审计数据不可清除。
- API Key 只能通过环境变量注入，不写入代码、文档、日志或数据库。

## 运行模式

### 离线安全模式

```bash
export MODEL_PROVIDER=offline_safe
export PYTHONPATH="$(pwd)"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
$env:MODEL_PROVIDER="offline_safe"
$env:PYTHONPATH=(Get-Location).Path
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

### DeepSeek / Qwen / Kimi 模型服务模式

示例为 DeepSeek。真实 Key 只在当前 shell 中设置，不要写入 `.env`、截图、日志或提交包。

```bash
export MODEL_PROVIDER=deepseek
export MODEL_API_BASE=https://api.deepseek.com
export MODEL_API_KEY=<your-api-key>
export MODEL_NAME=deepseek-chat
export PYTHONPATH="$(pwd)"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

支持的兼容变量：

- 新变量优先：`MODEL_PROVIDER`、`MODEL_API_BASE`、`MODEL_API_KEY`、`MODEL_NAME`
- 厂商 Key：`DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`、`MOONSHOT_API_KEY`
- 旧变量仍兼容：`LLM_PROVIDER`、`LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL`

配置缺失、超时或模型返回异常时，系统会安全降级到 `offline_safe`，不会直接执行命令，也不会放宽安全策略。

## 快速启动

### 1. 安装 Kylin 默认后端依赖

```bash
cd safeopsagent
python3 -m pip install -r backend/requirements-kylin.txt
```

如需运行自动化测试，可额外安装：

```bash
python3 -m pip install -r backend/requirements-dev.txt
```

Kylin 默认运行入口为 FastAPI 同源托管的 `/console/`，不需要 Node、Streamlit 或 pyarrow。Streamlit 是可选备用前端；只有明确需要时才安装完整 `backend/requirements.txt`。

### 2. 启动后端

```bash
export MODEL_PROVIDER=offline_safe
export PYTHONPATH="$(pwd)"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

访问：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/console/
```

Vue 控制台由 FastAPI 同源托管，已验证子路由：

```text
/console/
/console/monitor
/console/diagnosis
/console/security
/console/tools
/console/audit
```

### 3. 常用 API

```bash
curl http://127.0.0.1:8000/agent/status
curl http://127.0.0.1:8000/tools/list
```

正常只读诊断：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"check memory status"}'
```

多工具联合诊断与根因分析：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"check memory and disk and cpu"}'
```

危险请求拦截：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-danger","message":"rm -rf /"}'
```

审计回放：

```bash
curl http://127.0.0.1:8000/audit/logs
curl http://127.0.0.1:8000/audit/trace/{request_id}
```

监控大盘 API：

```bash
curl http://127.0.0.1:8000/monitor/overview     # 主机概览与健康判定
curl http://127.0.0.1:8000/monitor/metrics      # 指标时序 + 学习基线
curl http://127.0.0.1:8000/monitor/anomalies    # 基线偏离告警
curl -X POST http://127.0.0.1:8000/monitor/sample  # 立即采集一次
```

采样间隔由 `MONITOR_SAMPLE_INTERVAL` 控制（默认 60 秒，演示可设为 2）；
`MONITOR_SAMPLING_ENABLED=0` 可完全关闭后台采样。

### 4. MCP 协议接入（可选）

```bash
python3 -m pip install -r backend/requirements-mcp.txt
```

- **stdio 传输**：`python -m backend.mcp_server`
- **SSE 传输**：随主服务自动挂载 `/mcp/sse` 与 `/mcp/messages/`，与 HTTP API、Vue 控制台同源同端口

未安装 MCP SDK 时 SSE 静默跳过，stdio 与主服务均不受影响。所有 MCP 调用同样经过完整安全链路，不存在绕过通道。

## 工具清单

**基础感知工具（9 个 · 自动只读）**

`get_memory_status`、`get_cpu_status`、`disk_usage`、`process_list`、`network_status`、`get_port_usage`、`get_service_status`、`journal_query`、`large_file_scan`

**场景专项工具（3 个 · 自动只读）**

`config_drift_check`（配置漂移）、`zombie_process_check`（僵尸进程）、`disk_io_analysis`（磁盘 I/O）

**影响面预测工具（1 个 · 自动只读）**

`impact_analysis`（处置前推演影响面与句柄泄漏风险）

**安全清理工具（4 个）**

`safe_cleanup_scan`、`safe_cleanup_plan`（自动只读）；`safe_cleanup_quarantine`、`safe_cleanup_restore`（需人工确认）

## 项目结构

```text
safeopsagent/
├── backend/              # FastAPI、Agent、安全链路、工具、分析引擎、MCP
├── backend/static/console # Vue 构建产物，FastAPI /console/ 托管
├── frontend/             # Vue 控制台源码与 Streamlit 备用前端
├── scripts/              # 兼容性检查、性能测试、安全基准、打包脚本
├── docs/                 # 需求、设计、产品、测试、性能、部署、演示文档
├── deploy/               # systemd 部署脚本
└── README.md
```

## 交付文档

| 文档 | 路径 |
| --- | --- |
| 需求分析报告 | `docs/requirements-analysis.md` |
| **创新点说明** | `docs/innovation-highlights.md` |
| **安全不变式验证报告** | `docs/security-invariant-report.md` |
| 功能设计说明书 | `docs/functional-design.md` |
| 产品说明书 | `docs/product-manual.md` |
| 功能测试报告 | `docs/test-report.md` |
| 性能测试报告 | `docs/performance-test-report.md` |
| 安全设计说明 | `docs/security-design.md` |
| MCP 工具设计 | `docs/mcp-tool-design.md` |
| 麒麟部署文档 | `docs/deployment-kylin.md` |
| 兼容性矩阵 | `docs/compatibility-matrix.md` |
| 答辩 PPT 大纲 | `docs/presentation-outline.md` |
| 演示视频脚本 | `docs/demo-script.md` |
| 交付检查清单 | `docs/final-delivery-checklist.md` |

## 验证结论

本地最终验证：

```text
release: v1.3.0
pytest: 312 passed, 6 skipped, 1 warning
security benchmark: 64 cases, 63 evaluated, 1 skipped, FP=0, FN=0, pass_rate=100%
shell=True: no result
subprocess.run: only backend/executor/safe_executor.py
```

性能实测（离线安全模式，详见 `docs/performance-test-report.md`）：

```text
GET /health:            P95 2.5ms,  521 QPS
POST /chat 正常只读:     avg 16ms
POST /chat 危险拦截:     avg 13ms（预检即拒绝，比正常请求更快）
安全预检开销:            avg 0.15ms（占整链路 < 1%）
并发 1/4/8/16:          成功率 100%，零 5xx，峰值 94 QPS
进程峰值内存:            68 MB
```

官方 Kylin V11 LoongArch64 复验基线：

```text
OS: Kylin Linux Advanced Server V11 (Swan25)
Arch: loongarch64
Kernel: 6.6.0-32.7.v2505.ky11.loongarch64
Python: 3.11.6
backend import: import-ok
shell=True: no result
subprocess.run: only backend/executor/safe_executor.py
```

后端核心闭环：

```text
/health: pass
/agent/status: pass
/system/probe: pass
/tools/list: 17 tools
/chat multi-tool diagnosis: memory + CPU + disk pass
/chat rm -rf /: risk_score=100, reject, executed=false
/chat Prompt Injection: risk_score=100, reject, executed=false
/chat /etc/shadow: risk_score=100, reject, executed=false
/tools/call safe cleanup scan/plan: pass
/tools/confirm quarantine/restore: pass
confirmation replay/expiry/TOCTOU checks: pass
/audit/logs: pass
/audit/trace/{request_id}: pass
```

Vue 控制台：

```text
/console/: 200
/console/diagnosis: 200
/console/security: 200
/console/tools: 200
/console/audit: 200
Kylin LoongArch64 龙芯浏览器 headless screenshot: pass
```

DeepSeek 真实 Key 受控联调：

```text
agent_mode: model_api
model_provider: deepseek
model_vendor: DeepSeek
model_name: deepseek-chat
planner_source: domestic_model
normal request: check memory status -> get_memory_status, executed=true
rm -rf /: model precheck reject, executed=false
Prompt Injection: model precheck reject, executed=false
/etc/shadow: model precheck reject, executed=false
API / Audit Trace / Uvicorn log: no API Key leak
```

说明：

- 麒麟真机复验验证了核心安全闭环、多工具联合诊断、可恢复清理、危险拒绝、审计与 Vue 控制台。
- v1.3.0 新增的根因分析引擎、3 个场景工具与 MCP SSE 在本地完成 132 项自动化测试验证；建议在麒麟目标机重跑 `python -m pytest -q` 与 `python scripts/performance_test.py` 补充真机基线。
- DeepSeek 真实 Key 仅通过受控 shell 环境变量注入，未写入配置文件或交付包。

## 测试与验证脚本

```bash
# 自动化测试
python -m pytest -q

# 安全对抗基准
python scripts/run_security_benchmark.py

# 性能测试（自动生成 docs/performance-test-report.md）
python scripts/performance_test.py

# 安全不变式验证（失败时非零退出，可作发布门禁）
python scripts/verify_invariants.py

# 环境兼容性检查
python scripts/compatibility_check.py
```

## 打包

```bash
python scripts/package-final.py
```

默认生成 `../safeopsagent-<commit>-final-delivery.tar.gz`。打包脚本会保留顶层 `safeopsagent/` 目录，并排除：

- `.git`
- `.venv` / `.venv-frontend`
- `node_modules`
- `__pycache__`
- `.pytest_cache`
- 运行时 `data/`
- `audit.db`
- `.env`

## 能力边界

以下能力**不在本项目范围内**，这是明确的设计选择而非未完成项：

- **不提供永久删除**：不可逆操作违背安全可控原则，只提供同文件系统可恢复隔离与恢复。
- **不提供自动重启 / 自愈**：写操作的处置权保留给管理员，系统只给建议和 dry-run 计划。
- **不做内核级修改**：用户态运行，不需要 root，不使用 eBPF。
- **不包含本地大模型 / RAG / ModelHub**：与安全控制面核心命题正交，且对 LoongArch 算力要求过高。
- **不包含 openGauss 适配**：审计数据量级用 SQLite 完全满足，引入重型依赖违背最小部署原则。
- **不包含多租户 / RBAC**：产品定位为单机安全运维 Agent，不是多租户平台。

已知的工程约束：

- 审计写入使用进程内锁串行化，单进程并发吞吐存在上限；多进程部署需要替换为共享存储后端。
- Session 与 confirmation token 保存在进程内存中，多进程部署需要共享状态。
- Streamlit 保留为开发/备用展示入口，Kylin 主展示路径为 FastAPI `/console/`。
