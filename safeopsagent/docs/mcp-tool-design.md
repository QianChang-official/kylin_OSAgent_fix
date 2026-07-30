# SafeOpsAgent MCP-style 工具调用设计

本文档说明 SafeOpsAgent 当前的 Tool Registry、`/tools/list`、`/tools/call`、`/tools/confirm` 设计，以及可选的标准 MCP stdio 最小子集适配层。

重要边界：

```text
当前项目已经具备 MCP-style Tool Registry + HTTP 工具发现与调用接口。
当前提供基于官方 Python SDK 的 MCP stdio 入口，以及挂载在 FastAPI `/mcp` 下的可选 SSE 入口。
HTTP MCP 只能复用主服务的 Cookie、CSRF 与 CORS 边界；独立无认证 SSE 服务失败关闭。
当前不声明为完整生产级 MCP 平台；只有在安装可选 SDK 后，才运行真实 stdio initialize、tools/list 和 tools/call 互操作测试。
```

## 1. 设计目标

目标：

- 工具可发现。
- 参数有 schema。
- 调用入口统一。
- 工具执行受 Guardrail、RiskScorer、SafeExecutor 约束。
- 执行结果进入 Audit Trace。
- 模型不能直接执行系统命令。

当前链路：

```text
Client / Agent / Mock Provider
  -> GET /tools/list
  -> POST /tools/call
  -> POST /tools/confirm (仅中风险确认时使用)
  -> ToolRegistry.validate_args()
  -> Guardrail
  -> RiskScorer
  -> ToolRegistry.call()
  -> SafeExecutor
  -> AuditLogger

MCP Client
  -> backend/mcp_server.py (stdio)
  -> backend/mcp_adapter.py
  -> POST /tools/call 或 POST /tools/confirm 的内部 handler
  -> 复用同一条安全链路
```

## 2. Tool Registry

位置：

```text
backend/tools/registry.py
```

核心结构：

```python
ToolSchema(
    name: str,
    description: str,
    input_schema: dict
)
```

```python
ToolResult(
    tool: str,
    status: str,
    data: Any,
    raw_output: str,
    error: str,
    audit: dict
)
```

核心方法：

- `register(schema, handler)`
- `list_tools()`
- `get_schema(name)`
- `validate_args(name, args)`
- `call(name, args)`

## 3. 工具发现：GET /tools/list

接口：

```text
GET /tools/list
```

返回内容：

- 工具名。
- 工具描述。
- 输入 schema。

用途：

- Agent 获取可用工具列表。
- Mock Provider 按可用工具选择建议。
- 外部客户端查看当前系统能力。

## 4. 工具调用：POST /tools/call

接口：

```text
POST /tools/call
```

请求格式：

```json
{
  "tool_name": "get_memory_status",
  "arguments": {},
  "session_id": "demo"
}
```

响应核心字段：

```json
{
  "success": true,
  "request_id": "xxxxxxxx",
  "tool_name": "get_memory_status",
  "arguments": {},
  "risk_score": 10,
  "risk_level": "low",
  "legacy_risk_level": 1,
  "security_decision": "allow",
  "security_reason": "executed",
  "result": {},
  "error": "",
  "rule_hits": {}
}
```

三态安全决策：

| security_decision | 行为 |
| --- | --- |
| `allow` | 直接执行 Tool |
| `confirm` | 不执行 Tool，返回 `confirmation_required`、`confirmation_token` 和 `dry_run_result` |
| `reject` | 拒绝执行，不生成可执行 token |

`confirm` 响应中的 `dry_run_result` 只描述计划执行信息和风险解释，不调用 SafeExecutor，不产生系统副作用。

异常与阻断路径：

- 工具不存在：结构化错误，`security_decision=reject`。
- 参数非法：结构化错误，Tool 不执行。
- Guardrail 阻断：Tool 不执行。
- Tool 异常：结构化错误，不让 API 直接 500 崩溃。
- 工具输出危险：输出检查阻断，并写入审计。

## 5. 人工确认：POST /tools/confirm

接口：

```text
POST /tools/confirm
```

请求格式：

```json
{
  "confirmation_token": "xxxxxxxx",
  "session_id": "demo"
}
```

设计边界：

- `/tools/confirm` 只接收 token，不允许用户替换 `tool_name` 或 `arguments`。
- token 来源于 `/tools/call` 的 `security_decision=confirm` dry-run 响应。
- token 内存存储，默认 300 秒过期。
- token 一次性使用，确认后不能重复执行。
- 确认执行前会重新进行 schema 校验、Guardrail 和 RiskScorer。
- 如果重新评分为 `reject` / `forbidden`，仍然拒绝执行。
- Tool 执行仍通过 Tool Registry 和 SafeExecutor。
- Audit Trace 会记录 `confirmation_requested` 和 `confirmation_approved`，并关联 `original_request_id`。

当前边界：

- M13 只完成 `/tools/call` + `/tools/confirm` 闭环。
- `/chat` 尚未接入 confirm 交互，属于后续扩展。

## 6. 已注册工具

当前核心 OS 感知工具：

| 工具名 | 用途 |
| --- | --- |
| `disk_usage` | 查看磁盘空间 |
| `process_list` | 查看进程列表 |
| `network_status` | 查看网络状态 |
| `journal_query` | 查询系统日志 |
| `large_file_scan` | 扫描允许目录内的大文件 |
| `get_port_usage` | 查询端口占用 |
| `get_memory_status` | 查询内存状态 |
| `get_service_status` | 查询 systemd 服务状态 |
| `get_cpu_status` | 查询 CPU 使用率、系统负载和高占用进程 |
| `safe_cleanup_scan` | 只读扫描临时文件候选 |
| `safe_cleanup_plan` | 生成绑定文件元数据的 dry-run 计划 |
| `safe_cleanup_quarantine` | 人工确认后执行同文件系统可恢复隔离 |
| `safe_cleanup_restore` | 人工确认后恢复隔离文件 |

所有涉及系统命令的工具必须通过 SafeExecutor。

## 7. Schema 示例

无参数工具：

```json
{
  "name": "get_memory_status",
  "description": "Query system memory status in MB",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

带参数工具：

```json
{
  "tool_name": "get_port_usage",
  "arguments": {
    "port": 8080
  }
}
```

参数要求：

- `port` 必须是整数。
- 范围为 1-65535。
- 字符串或注入片段会被拒绝。

## 8. 安全调用链路

`/tools/call` 并不直接执行工具，而是经过完整安全链路：

```text
1. Tool 是否存在
2. JSON schema 参数校验
3. Guardrail 输入检查
4. Guardrail 工具选择检查
5. Guardrail 参数检查
6. RiskScorer 0-100 风险评分
7. allow / confirm / reject 三态决策
8. confirm 时返回 dry-run，等待 /tools/confirm
9. ToolRegistry.call()
10. Tool 内部调用 SafeExecutor
11. Guardrail 输出检查
12. AuditLogger 写入审计
13. 返回结构化响应
```

这条链路保证：

- 模型不能直接执行 Shell。
- 未注册工具不能执行。
- 参数非法不能执行。
- 高危输入不能执行。
- 中风险操作需要人工确认后才能执行。
- 工具执行结果可审计。

## 9. 与 Mock Provider 的关系

Mock Provider 的角色：

- 根据自然语言建议 `tool_name` 和 `arguments`。
- 不直接执行工具。
- 不绕过 Tool Registry。
- 不绕过 Guardrail。
- 不绕过 SafeExecutor。
- 不绕过 AuditLogger。

因此，即使使用 Mock Provider，安全链路仍然完整。

## 10. 与标准 MCP Server 的关系

当前已完成：

- MCP-style Tool Registry。
- `GET /tools/list`。
- `POST /tools/call`。
- `POST /tools/confirm`。
- 标准 MCP stdio 最小子集：`backend/mcp_server.py`。
- 纯 Python MCP adapter：`backend/mcp_adapter.py`。
- 工具 schema。
- 统一工具调用。
- 中风险 confirm / dry-run。
- 安全检查。
- 审计追踪。

MCP stdio 最小子集的定位：

- 只作为协议入口，不重写工具系统。
- `tools/list` 映射现有 `ToolRegistry.list_tools()`。
- `tools/call` 普通工具调用映射到现有 `/tools/call` handler。
- 额外暴露 `safeops_confirm_tool`，用于把 MCP 确认请求映射到现有 `/tools/confirm` handler。
- 中风险请求仍返回 `confirmation_required`、`confirmation_token` 和 `dry_run_result`，不执行工具。
- 高危 `reject` / `forbidden` 仍由 Guardrail 和 RiskScorer 阻断，不能通过 MCP 绕过。
- Audit Trace 仍由现有 `/tools/call` 和 `/tools/confirm` 写入。

启动方式：

```powershell
cd safeopsagent
python -m pip install -r backend/requirements-mcp.txt
$env:PYTHONPATH=(Get-Location).Path
python -m backend.mcp_server
```

依赖边界：

- 默认 `backend/requirements.txt` 不包含 MCP SDK。
- MCP SDK 仅放在 `backend/requirements-mcp.txt`，作为可选依赖。
- 未安装 MCP SDK 时，`backend.app` 导入和默认测试不受影响。
- 麒麟 V11 / LoongArch64 最小冒烟路径仍优先使用 FastAPI `/tools/list`、`/tools/call`、`/tools/confirm`。
- 当前不声明 MCP SDK 已在官方 Kylin V11 LoongArch64 环境实测通过。

当前未实现：

- MCP SSE transport。
- MCP Streamable HTTP transport。
- 生产级 MCP 鉴权、租户隔离和长连接治理。
- `/chat` confirm 交互接入。

后续扩展路线：

```text
现有 ToolSchema / ToolResult
  -> 映射为 MCP Tool 定义
  -> 暴露标准 MCP transport
  -> 复用 Guardrail / RiskScorer / SafeExecutor / AuditLogger
```

当前已完成标准 MCP stdio 最小子集；完整生产级 MCP 平台仍属于后续扩展。

## 11. 当前边界

已完成：

- 工具发现。
- 工具 schema。
- 统一工具调用。
- 中风险 confirm / dry-run。
- 工具调用安全检查。
- SafeExecutor 安全执行。
- Audit Trace。
- Session TTL。
- MCP stdio 传输。
- **MCP SSE / Streamable HTTP transport**（`/mcp/sse` + `/mcp/messages/`，与 HTTP API 同源同端口）。

待实现 / 后续扩展：

- 生产级 MCP 鉴权和会话治理。
- `/chat` confirm 接入。
- 官方 Kylin 环境中的 MCP SDK 完整实测。
- Streamlit 前端系统性测试。
- 长期压测和稳定性测试。

总结：

```text
当前系统已经具备 MCP-style 安全工具调用闭环。
当前已提供标准 MCP stdio 最小子集适配层。
它复用现有安全链路，但不等同于完整生产级 MCP 平台。
```
