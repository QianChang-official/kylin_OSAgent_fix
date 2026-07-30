# SafeOpsAgent 安全设计说明

SafeOpsAgent 的安全目标是让大模型能辅助运维，但不能绕过安全规则直接操作系统。系统将“模型推理面”和“安全控制面”分离：模型只负责自然语言理解、工具规划和结果总结；安全控制面负责意图过滤、风险评分、工具白名单、参数校验、最小权限执行与审计追踪。

## 1. 总体链路

```text
用户自然语言请求
  -> Guardrail 本地安全预检
  -> 国产模型适配层 / 离线安全规划器
  -> Tool Registry 工具白名单与参数校验
  -> RiskScorer 0-100 风险决策
  -> confirm / dry-run 人工确认
  -> SafeExecutor 最小权限执行
  -> 输出安全检查
  -> Audit Trace v2 全链路审计
```

设计原则：

- 模型不能直接执行 shell。
- 所有系统命令只能通过 SafeExecutor。
- 自动执行范围仅限只读运维工具。
- 高风险请求在模型调用或工具执行前被拒绝。
- 每次请求都有 `request_id` 和审计 Trace。
- API Key 只通过环境变量注入，不写入配置、日志、响应或审计。

## 2. 国产模型适配层

当前模型层支持：

| 模式 | 对外字段 | 说明 |
| --- | --- | --- |
| 国产模型服务模式 | `agent_mode=model_api`，`planner_source=domestic_model` | 支持 DeepSeek、千问/Qwen、Kimi，以及自定义兼容式模型服务。 |
| 离线安全规划器 | `agent_mode=offline_safe`，`planner_source=offline_safe` | 无外网、无 API Key 或模型异常时自动降级，仍可演示安全链路。 |

对外稳定字段：

- `agent_mode`: `model_api` / `offline_safe`
- `model_provider`: `deepseek` / `qwen` / `kimi` / `custom` / `offline_safe`
- `model_vendor`: `DeepSeek` / `千问` / `Kimi` / `自定义模型服务` / `内置安全规划器`
- `model_name`: 配置模型名或 `offline`
- `planner_source`: `domestic_model` / `offline_safe`

模型 Provider 只返回：

- `intent`
- `tool_plan`
- `planner_confidence`
- `planner_explanation`

Provider 不返回模型思维链，不生成 shell 命令，不直接执行工具。

## 3. 前置安全拦截

Guardrail 是本地前置安全护栏，优先级高于模型调用。它会识别并拒绝：

- 危险命令：删除、格式化、覆盖、重启、关闭、杀进程等。
- 下载后执行：`curl | sh`、`wget -O- | sh` 等。
- 受保护路径：`/etc/shadow`、`/etc/passwd`、磁盘设备等敏感目标。
- Prompt Injection：忽略规则、输出 system prompt、绕过审计、关闭安全检查等。
- 工具参数和工具输出中的危险模式。

官方 Kylin 复验中，`rm -rf /`、Prompt Injection、`/etc/shadow` 均在模型调用前拒绝，风险分为 100，未执行系统命令。

## 4. 风险评分与三态决策

RiskScorer 将请求、工具、参数、规则命中和输出检查统一映射为 0-100 风险分：

```json
{
  "risk_score": 100,
  "risk_level": "forbidden",
  "legacy_risk_level": 5,
  "security_decision": "reject",
  "matched_rules": []
}
```

安全决策：

| 决策 | 含义 |
| --- | --- |
| `allow` | 低风险只读工具可直接执行。 |
| `confirm` | 中风险请求只返回 dry-run 和确认 token，不直接执行。 |
| `reject` | 高风险或禁止请求被拒绝。 |

`legacy_risk_level` 仅用于旧接口兼容，主展示以 `risk_score`、`risk_level`、`security_decision` 为准。

## 5. Tool Registry

Tool Registry 管理受控工具：

- 工具白名单。
- 参数 schema。
- 参数范围和正则校验。
- 工具描述和统一调用入口。

当前自动执行工具均为只读运维工具，或不会修改文件的清理扫描/计划：

- `get_memory_status`
- `disk_usage`
- `process_list`
- `network_status`
- `get_port_usage`
- `get_service_status`
- `journal_query`
- `large_file_scan`
- `get_cpu_status`
- `config_drift_check`
- `zombie_process_check`
- `disk_io_analysis`
- `safe_cleanup_scan`
- `safe_cleanup_plan`

系统不提供永久删除、自动重启、自动修改配置或自愈能力。`safe_cleanup_quarantine` 和 `safe_cleanup_restore` 仅处理临时目录白名单中的普通文件，必须经过 dry-run、一次性确认、计划哈希、移动前后文件元数据复验和受控目录权限检查，并使用同文件系统可恢复移动。

## 6. SafeExecutor

SafeExecutor 是系统命令执行的唯一入口：

- 只接受 `list[str]` 命令。
- 禁止字符串命令。
- 禁止 `shell=True`。
- 主命令必须在 allowlist 中。
- 整条命令检查危险 token。
- 设置 timeout。
- 截断 stdout / stderr。
- 返回结构化 `CommandResult`。
- 记录执行用户。

官方复验和本地静态检查均确认：`shell=True` 无结果，`subprocess.run` 仅出现在 `backend/executor/safe_executor.py`。

## 7. confirm / dry-run

对于中风险工具调用，`/tools/call` 不直接执行，而是返回：

- `confirmation_required=true`
- `confirmation_token`
- `dry_run_result`

用户通过 `/tools/confirm` 提交 token 后，系统会重新执行 schema 校验、Guardrail 和 RiskScorer。确认接口不能绕过安全链路；如果重新评分为 `reject` 或 `forbidden`，仍会拒绝执行。token 具有过期时间，并在锁内完成检查与一次性消费，防止并发重放导致重复执行。

当前 `/chat` 主要用于只读自动诊断与高风险拒绝演示，完整 `/chat` confirm 交互仍是后续扩展。

## 8. Audit Trace v2

Audit Trace 记录决策摘要和链路事件，不记录模型思维链。典型事件包括：

- receive_input
- precheck
- agent_planning
- tool_plan_created
- tool_validated
- tool_executed
- result_summarized
- output_checked
- response_generated
- audit_saved

`/audit/logs` 用于查看审计列表，`/audit/trace/{request_id}` 用于回放单次请求。

DeepSeek 受控联调中已检查：API 响应、Audit Trace、Uvicorn log 均未泄漏 API Key。

## 9. Kylin 与环境能力限制

在 Windows 或非完整 Linux 环境中，部分系统命令可能缺失，例如 `free`、`ss`、`journalctl`、`systemctl`。此时工具会返回 environment_limited 或结构化错误，表示运行环境能力受限，不代表安全链路失败。

官方 Kylin V11 LoongArch64（基线 `57d90f8`）已验证 CPU 诊断、多工具联合诊断、可恢复清理、危险请求拦截、审计追踪和 Vue `/console/`。v1.3.0 在此基础上新增跨工具根因分析引擎、三个场景工具与 MCP SSE 传输，安全主链路（Guardrail → RiskScorer → SafeExecutor → Audit）未做结构性改动。

## 10. 明确边界

以下能力**不在本项目范围内**，是明确的设计选择而非未完成项：

- **永久删除、自动重启、自动修复或自愈**：不可逆或无人确认的写操作违背安全可控原则，系统只提供 dry-run 计划、人工确认与可恢复隔离。
- **多租户、RBAC 权限体系**：产品定位为单机安全运维 Agent，不是多租户平台。
- **本地大模型 / ModelHub / RAG**：与安全控制面核心命题正交，且对 LoongArch 算力要求过高。
- **openGauss 国产数据库适配**：审计数据量级用 SQLite 完全满足，引入重型依赖违背最小部署原则。
- **内核级修改 / eBPF**：用户态运行，不需要 root。

以下为已知的工程约束：

- 审计写入使用进程内锁串行化，单进程并发吞吐存在上限；多进程部署需替换为共享存储后端。
- Session 与 confirmation token 保存在进程内存，多进程部署需共享状态。
- MCP SSE / stdio 传输依赖可选 MCP SDK；官方 Kylin 环境中的 MCP SDK 完整实测尚未执行。
- 长期压测、HA 与集群部署未纳入当前验证范围。
