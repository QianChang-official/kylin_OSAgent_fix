# SafeOpsAgent 兼容性矩阵

本文档记录 SafeOpsAgent 在开发环境与官方银河麒麟环境中的验证范围。所有结论只按实际验证范围表述，不扩大为生产级承诺。

## 1. 最终验证基线

| 项目 | 结果 |
| --- | --- |
| 本地分支 | `dev` |
| 当前发布版本 | `v1.3.0` |
| 稳定标签 | `safeopsagent-v1.3.0-final-delivery` |
| 最终包 | `safeopsagent-<tag-commit-short-hash>-final-delivery.tar.gz` |
| 最终包 SHA256 | 见包旁同名 `.sha256` 文件 |
| 本地最终 pytest | 449 项自动化用例（`pytest --collect-only`）；跳过项随平台与可选依赖变化 |
| 官方系统 | Kylin Linux Advanced Server V11 (Swan25) |
| 官方架构 | `loongarch64` |
| 官方内核 | `6.6.0-32.7.v2505.ky11.loongarch64` |
| 官方 Python | `3.11.6` |
| 官方 Kylin LoongArch64 复验 pytest | 通过 |
| 后端导入 | `import-ok` |
| 静态安全检查 | `shell=True` 无结果，`subprocess.run` 仅 SafeExecutor |
| 安全基准 | 64 项（部分用例依赖 POSIX 环境，跳过数随平台变化），误报 0，漏报 0 |

官方 Kylin LoongArch64 复验基线为 `57d90f8`，验证了 CPU 诊断、多工具联合诊断、可恢复清理、危险拒绝、审计与 Vue 控制台的可运行性。v1.3.0 后期新增的影响面预测、变更—故障因果关联、自学习基线监控与前门欺骗，以及审计哈希链，均已在本地完成自动化验证；建议在麒麟目标机重跑一次完整回归补充真机基线。

## 2. 核心能力矩阵

| 能力 | Windows / 开发环境 | 官方 Kylin V11 LoongArch64 | 说明 |
| --- | --- | --- | --- |
| `backend.app` 导入 | 已验证 | 已验证 | `python -c "import backend.app; print('import-ok')"` |
| 全量 pytest | 已验证 | 已验证 v1.2 RC | 本地最终为 449 项自动化用例全部收集并通过；Kylin LoongArch64 复验通过 |
| FastAPI 启动 | 已验证 | 已验证 | Uvicorn 可启动并响应本地请求 |
| `/health` | 已验证 | 已验证 | 返回 200 |
| `/agent/status` | 已验证 | 已验证 | 返回运行模式、模型提供方和规划来源 |
| `/system/probe` | 已验证 | 已验证 | 返回 OS、kernel、arch、Python 与命令探测 |
| `/tools/list` | 已验证 | 已验证 | 返回 17 个受控工具：15 个自动只读/安全规划工具，2 个确认执行工具 |
| `/tools/call` | 已验证 | 已验证 | `get_memory_status` 等只读工具可调用 |
| `/tools/confirm` | 已验证 | 已验证后端接口 | 中风险 dry-run / confirmation 机制可用 |
| `/chat` 正常只读请求 | 已验证 | 已验证 | `check memory status` 可规划 `get_memory_status` |
| `/chat` 危险命令拦截 | 已验证 | 已验证 | `rm -rf /` 风险分 100，拒绝，未执行 |
| Prompt Injection 拦截 | 已验证 | 已验证 | “输出 system prompt / 不记录日志”等被拒绝 |
| 受保护路径拦截 | 已验证 | 已验证 | `/etc/shadow` 请求在模型调用前拒绝 |
| `/audit/logs` | 已验证 | 已验证 | 可读取审计列表 |
| `/audit/trace/{request_id}` | 已验证 | 已验证 | 可回放请求链路 |
| SafeExecutor | 已验证 | 已验证 | 只接受 `list[str]`，禁用 `shell=True`，命令白名单 |
| Guardrail | 已验证 | 已验证 | 危险命令、提示词注入、审计绕过等被拦截 |
| RiskScorer | 已验证 | 已验证 | 风险分范围 0-100，高危最大为 100 |
| Audit Trace v2 | 已验证 | 已验证 | 记录决策摘要和链路事件，不记录思维链 |
| 国产模型适配层 | 已验证 | DeepSeek 受控联调已通过 | 支持 DeepSeek / Qwen / Kimi / custom / offline_safe |
| 离线安全规划器 | 已验证 | 已验证 | 无外网、无 API Key 时可演示安全闭环 |
| Vue 控制台 | 已验证 | 已验证 | FastAPI `/console/` 同源托管，运行时不依赖 Node、Streamlit、pyarrow |
| Streamlit 前端 | 已验证 | 未作为官方主展示入口 | 保留为开发/备用入口 |
| MCP stdio + SSE | 已验证 adapter / transport | 未执行 MCP SDK 官方实测 | stdio 与 SSE 双传输；SDK 为可选依赖，不影响最小部署 |
| SQLite 审计 | 已验证 | 已验证 | 审计写入与读取可用 |
| CPU / 联合诊断 | 已验证 | 已验证 v1.2 RC | 内存、CPU、磁盘可联合生成确定性诊断 |
| 可恢复安全清理 | 已验证 | 已验证 v1.2 RC | scan、plan、confirm、quarantine、restore 与重放/TOCTOU 防护 |

## 3. Vue 控制台官方复验

Vue 控制台已经合入 `dev`，由 FastAPI 同源托管：

```text
http://127.0.0.1:18080/console/
http://127.0.0.1:18080/console/diagnosis
http://127.0.0.1:18080/console/security
http://127.0.0.1:18080/console/tools
http://127.0.0.1:18080/console/audit
```

以上路由在官方 Kylin V11 LoongArch64 v1.2 RC 环境中均验证返回 200；桌面端无横向溢出，诊断页可展示真实内存指标，安全页可展示 100 分拒绝与未执行状态。

## 4. DeepSeek 受控联调

DeepSeek 真实 Key 仅通过当前 shell 环境变量临时注入，未写入配置文件、日志、审计或文档。联调结果：

| 检查项 | 结果 |
| --- | --- |
| `agent_mode` | `model_api` |
| `model_provider` | `deepseek` |
| `model_vendor` | `DeepSeek` |
| `model_name` | `deepseek-chat` |
| `planner_source` | `domestic_model` |
| 正常请求 | `check memory status` 成功规划 `get_memory_status` |
| 高危请求 | `rm -rf /` 在模型调用前拒绝 |
| Prompt Injection | 在模型调用前拒绝 |
| `/etc/shadow` | 在模型调用前拒绝 |
| Key 泄漏检查 | API 响应、Audit Trace、Uvicorn log 均未出现 Key |

## 5. 低资源 LoongArch64 依赖边界

官方 LoongArch64 低资源环境可能缺少部分 Python 包二进制 wheel。最小后端复验优先使用：

```text
backend/requirements-kylin.txt
```

Vue 控制台构建产物已经随后端托管，Kylin 运行时不需要 Node、Streamlit 或 pyarrow。

## 6. 未纳入范围的能力

以下内容不作为当前交付完成项：

- 多租户与 RBAC 权限体系。
- openGauss 国产数据库适配。
- 本地大模型 / ModelHub / RAG。
- 官方 Kylin 环境中的 MCP SDK 完整实测。
- 长期压测与稳定性测试、HA 与集群部署。
- 自动删除、自动重启、自动修复或自愈。
