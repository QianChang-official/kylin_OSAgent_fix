# PPT 最终验证页素材

可作为答辩 PPT 的“最终验证结果”页面使用。内容只记录已验证事实，不扩大为生产级承诺。

## 页面标题

SafeOpsAgent 最终验证结果

## 一句话结论

SafeOpsAgent 已在官方银河麒麟 V11 LoongArch64 环境完成安全智能运维核心闭环复验：自然语言请求、风险预检、工具规划、最小权限执行、危险请求拒绝、审计追踪与 Vue 控制台展示均可运行。

## 验证环境

| 项目 | 结果 |
| --- | --- |
| OS | Kylin Linux Advanced Server V11 (Swan25) |
| 架构 | loongarch64 |
| 内核 | 6.6.0-32.7.v2505.ky11.loongarch64 |
| Python | 3.11.6 |
| 当前发布版本 | v1.3.0 |
| 稳定标签 | safeopsagent-v1.3.0-final-delivery |
| 最终包 | safeopsagent-&lt;tag-commit-short-hash&gt;-final-delivery.tar.gz |
| 包校验值 | 见包旁同名 `.sha256` 文件 |
| Kylin 真机复验基线 | 57d90f8 |

## 自动化与静态检查

| 检查项 | 结果 |
| --- | --- |
| 后端导入 | import-ok |
| 本地最终 pytest | 449 项自动化用例，0 失败 |
| Kylin LoongArch64 复验 | 通过 |
| 安全基准 | 64 项（部分用例依赖 POSIX 环境，跳过数随平台变化），误报 0，漏报 0 |
| `shell=True` | 无结果 |
| `subprocess.run` | 仅 SafeExecutor |
| API Key 泄漏 | API / Audit Trace / Uvicorn log 未发现 Key |

## 核心链路验证

| 场景 | 结果 |
| --- | --- |
| 正常只读请求 | `check memory status` 成功规划 `get_memory_status` |
| 危险命令 | `rm -rf /` 风险分 100，拒绝，未执行 |
| Prompt Injection | 输出 system prompt / 不记录日志被拒绝 |
| 受保护路径 | `/etc/shadow` 请求在模型调用前拒绝 |
| 审计追踪 | `/audit/logs` 与 `/audit/trace/{request_id}` 可回放 |

## Vue 控制台验证

| 路由 | 结果 |
| --- | --- |
| `/console/` | 200 |
| `/console/diagnosis` | 200 |
| `/console/security` | 200 |
| `/console/tools` | 200 |
| `/console/audit` | 200 |

说明：Vue 控制台由 FastAPI 同源托管，Kylin 运行时不依赖 Node、Streamlit 或 pyarrow。

边界：Kylin 真机结果来自基线 `57d90f8`；v1.3.0 后期新增能力已在本地完成自动化验证，建议在目标机补跑一次完整回归。

## 国产模型联调

| 字段 | 结果 |
| --- | --- |
| `agent_mode` | `model_api` |
| `model_provider` | `deepseek` |
| `model_vendor` | `DeepSeek` |
| `model_name` | `deepseek-chat` |
| `planner_source` | `domestic_model` |

安全结论：DeepSeek 真实 Key 仅通过 shell 环境变量临时注入；危险命令、Prompt Injection、`/etc/shadow` 均在模型调用前拒绝。

## 边界说明

以下能力不在项目范围内，属于明确的设计选择：

- 不提供永久删除、自动重启、自动修复或自愈；处置只到可恢复隔离，且需人工确认。
- 不包含多租户 / RBAC 权限体系、openGauss、本地大模型、ModelHub、RAG。
- 用户态运行，不做内核级修改。

已知工程约束：审计写入为进程内锁串行化，多进程部署需替换共享存储后端；官方 Kylin 环境中的 MCP SDK 完整实测尚未执行。
