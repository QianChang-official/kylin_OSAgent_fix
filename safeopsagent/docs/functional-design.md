# SafeOpsAgent 功能设计说明书

**项目名称**：SafeOpsAgent — 面向麒麟操作系统的安全智能运维 Agent
**版本**：v1.3.0
**文档类型**：功能设计说明书

---

## 1. 设计目标与原则

### 1.1 核心设计命题

> 让大模型可以理解运维需求并规划操作，但**永远不能**绕过安全控制面直接操作系统。

### 1.2 五条设计原则

| 原则 | 含义 | 设计落点 |
| --- | --- | --- |
| **模型不可信** | 模型输出一律视为不可信输入，需二次校验 | 工具规划必须过 Registry 白名单 + Schema 校验 + 风险评分 |
| **前置拦截** | 危险请求在模型调用之前就被拒绝 | Guardrail 预检位于 LLM 调用之前，而非之后 |
| **最小权限** | 命令白名单化，禁止 Shell 解释 | SafeExecutor 统一收口，`shell=False` 硬编码 |
| **可恢复优先** | 不提供不可逆操作 | 清理只提供同文件系统隔离 + 恢复，无永久删除 |
| **全程可审计** | 允许、拒绝、降级都留痕 | 每次请求生成 request_id，写入 append-only 审计 |

---

## 2. 系统架构设计

### 2.1 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│                     表现层 (B/S)                              │
│  Vue 3 控制台（FastAPI 同源托管 /console/）                    │
│  工作台 │ 智能诊断 │ 安全中心 │ 工具能力 │ 审计追踪            │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP / JSON
┌────────────────────────▼─────────────────────────────────────┐
│                    接口层 (FastAPI)                           │
│  /chat  /tools/list  /tools/call  /tools/confirm             │
│  /agent/status  /system/probe  /audit/logs  /audit/trace     │
│  /mcp/sse  /mcp/messages（MCP SSE 传输，可选）                │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                 编排层 (AgentOrchestrator)                    │
│  会话管理 → 安全预检 → 模型规划 → 工具执行 → 诊断 → 审计       │
└──┬──────────┬──────────┬──────────┬──────────┬───────────────┘
   │          │          │          │          │
┌──▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼─────┐ ┌──▼──────────┐
│安全层 │ │模型层  │ │工具层  │ │分析层   │ │审计层       │
│       │ │        │ │        │ │         │ │             │
│Guard- │ │国产模型│ │Tool    │ │诊断引擎 │ │AuditLogger  │
│rail   │ │网关    │ │Registry│ │根因引擎 │ │Trace v2     │
│Risk-  │ │离线安全│ │16 工具 │ │         │ │SQLite       │
│Scorer │ │规划器  │ │        │ │         │ │append-only  │
└───┬───┘ └────────┘ └───┬────┘ └─────────┘ └─────────────┘
    │                    │
    │              ┌─────▼──────────┐
    └─────────────►│ SafeExecutor   │
                   │ 命令白名单     │
                   │ shell=False    │
                   │ 超时+输出截断  │
                   └─────┬──────────┘
                         │
                   ┌─────▼──────────┐
                   │ 麒麟操作系统   │
                   └────────────────┘
```

### 2.2 模块清单

| 层次 | 模块 | 路径 | 职责 |
| --- | --- | --- | --- |
| 接口层 | FastAPI App | `backend/app.py` | REST API、控制台托管、确认令牌管理 |
| 编排层 | AgentOrchestrator | `backend/agent/orchestrator.py` | 全链路编排、会话管理、多工具规划 |
| 安全层 | Guardrail | `backend/security/guardrail.py` | 输入/工具/参数/输出四道安全检查 |
| 安全层 | RiskScorer | `backend/security/risk_score.py` | 0-100 风险量化与三态决策 |
| 安全层 | RuleLabels | `backend/security/rule_labels.py` | 规则命中转可读中文标签 |
| 安全层 | Benchmark | `backend/security/benchmark.py` | 64 项安全对抗基准评测 |
| 执行层 | SafeExecutor | `backend/executor/safe_executor.py` | 唯一系统命令出口，最小权限执行 |
| 模型层 | DomesticModelGateway | `backend/llm/domestic_model_gateway.py` | 国产模型配置解析与安全降级 |
| 模型层 | 离线安全规划器 | `backend/llm/mock_provider.py` | 无网络时的确定性规划 |
| 工具层 | ToolRegistry | `backend/tools/registry.py` | 工具注册、发现、Schema 校验、调用 |
| 工具层 | 16 个工具 | `backend/tools/*.py` | OS 感知与运维能力实现 |
| 分析层 | RecommendationEngine | `backend/analysis/recommendation_engine.py` | 单工具结果解析与诊断结论 |
| 分析层 | RootCauseEngine | `backend/analysis/root_cause_engine.py` | 跨工具证据关联与根因链 |
| 审计层 | AuditLogger | `backend/audit/logger.py` | Trace v2 审计写入与回放 |
| 感知层 | OSProbe | `backend/osprobe/probe.py` | 运行环境能力探测 |
| 协议层 | MCPAdapter | `backend/mcp_adapter.py` | MCP 协议映射（纯 Python 实现） |
| 协议层 | MCPServer | `backend/mcp_server.py` | MCP stdio + SSE 传输 |
| 业务层 | CleanupService | `backend/cleanup/service.py` | 可恢复隔离与恢复 |

---

## 3. 核心流程设计

### 3.1 自然语言请求主流程

```
用户输入
   │
   ▼
┌─────────────────────────────────────┐
│ ① 会话上下文加载                     │
│   TTL 过期检查 → 上下文裁剪          │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ ② Guardrail 输入预检                 │  ◄── 关键：在模型调用之前
│   危险命令 / Prompt Injection /      │
│   受保护路径 / Shell 注入字符        │
└──────────────┬──────────────────────┘
               ▼
        ┌──────────────┐
        │ risk >= 100? │──── 是 ──►  拒绝 + 写审计 + 返回替代建议
        └──────┬───────┘             （模型完全不被调用）
               │ 否
               ▼
┌─────────────────────────────────────┐
│ ③ 模型规划                           │
│   国产模型 API / 离线安全规划器      │
│   输出 tool_plan（最多 3 个工具）    │
│   异常/超时/非法 JSON → 降级 offline │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ ④ 工具计划逐项校验（循环）            │
│   a. 是否在 /chat 只读白名单（14 个） │
│   b. Registry Schema 参数校验        │
│   c. Guardrail 工具选择 + 参数检查   │
│   d. RiskScorer 评分 → 三态决策      │
└──────────────┬──────────────────────┘
               ▼
        ┌──────────────┐
        │ decision?    │
        └──┬────┬───┬──┘
     allow │    │   │ reject → 标记 blocked，跳过执行
           │    │ confirm → dry-run + 一次性令牌
           ▼
┌─────────────────────────────────────┐
│ ⑤ SafeExecutor 执行                  │
│   命令白名单 + shell=False +         │
│   超时 + 输出截断 + 执行用户记录     │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ ⑥ 工具输出安全复检                   │
│   输出含危险内容 → 阻断返回          │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ ⑦ 智能分析                           │
│   RecommendationEngine 单工具诊断    │
│   RootCauseEngine 跨工具根因关联     │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ ⑧ Audit Trace 写入                   │
│   request_id + 完整事件链 + 决策摘要 │
└──────────────┬──────────────────────┘
               ▼
          结构化响应
```

### 3.2 关键设计决策

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 安全预检位置 | **模型调用之前** | 危险输入不给模型任何被诱导的机会；同时节省 token 与延迟 |
| 工具执行范围 | `/chat` 仅自动执行 14 个只读工具 | 写操作必须走 `/tools/call` + 人工确认，不能由自然语言直接触发 |
| 模型故障处理 | 降级到离线安全规划器 | 绝不因模型不可用而放宽安全策略，也不中断服务 |
| 多工具上限 | 最多 3 个 | 平衡诊断完整度与响应延迟、审计可读性 |
| 审计存储 | SQLite append-only，按日分表 | 零外部依赖，适配离线麒麟环境；不提供清除接口 |
| 确认令牌 | 一次性 + TTL + 重新校验 | 防重放、防过期、防 TOCTOU（确认时重新评分，风险升高则拒绝） |

---

## 4. 安全护栏设计

### 4.1 四道检查

| 检查点 | 方法 | 检测内容 |
| --- | --- | --- |
| 输入检查 | `check_input()` | 危险命令 token、Prompt Injection 模板、受保护路径、Shell 注入字符、路径穿越 |
| 工具选择检查 | `validate_tool_selection()` | 工具是否在注册表白名单内 |
| 参数检查 | `validate_tool_args()` | 参数中的危险路径、越权目录、类型与约束 |
| 输出检查 | `check_tool_output()` | 工具输出中的危险命令回显、注入内容 |

### 4.2 风险量化模型

**分数合成规则**：`最终分 = max(检查基线分, 工具基线分, 规则权重分)`

工具基线分（部分）：

| 工具 | 基线分 | 工具 | 基线分 |
| --- | --- | --- | --- |
| `get_memory_status` | 10 | `journal_query` | 22 |
| `disk_usage` | 12 | `get_service_status` | 25 |
| `get_cpu_status` | 14 | `safe_cleanup_scan` | 30 |
| `disk_io_analysis` | 14 | `large_file_scan` | 40 |
| `process_list` | 16 | `safe_cleanup_plan` | 40 |
| `zombie_process_check` | 16 | `safe_cleanup_quarantine` | 75 |
| `get_port_usage` | 18 | `safe_cleanup_restore` | 75 |
| `config_drift_check` | 20 | 未注册工具 | 30（默认） |

规则权重（部分）：

| 规则 | 权重 | 规则 | 权重 |
| --- | --- | --- | --- |
| `delete_command` | 100 | `dangerous_path_in_arg` | 75 |
| `dangerous_cmd` | 100 | `dangerous_path` | 70 |
| `shell_injection_char` | 100 | `output_contains_delete_cmd` | 70 |
| `protected_credential` | 100 | `injection_template` | 65 |
| `path_traversal` | 100 | `output_injection` | 60 |
| `tool_not_in_whitelist` | 100 | `schema_validation` | 100 |

### 4.3 风险分档与决策

| 分数区间 | 风险等级 | 决策 | 行为 |
| --- | --- | --- | --- |
| 0-39 | `low` | `allow` | 直接执行 |
| 40-69 | `medium` | `confirm` | dry-run + 一次性令牌人工确认 |
| 70-99 | `high` | `confirm` / `reject` | 视规则命中决定 |
| 100 | `forbidden` | `reject` | 拒绝执行，写审计 |

### 4.4 SafeExecutor 约束

```python
subprocess.run(
    valid_command,      # 必须是 list，拒绝字符串
    shell=False,        # 硬编码，禁止 Shell 解释
    capture_output=True,
    text=True,
    timeout=effective_timeout,   # 强制超时
)
```

| 约束 | 实现 |
| --- | --- |
| 拒绝字符串命令 | 只接受 `list[str]`，防止 Shell 拼接注入 |
| 命令白名单 | `config.COMMAND_WHITELIST` 校验首个 token |
| 命令黑名单 | `config.COMMAND_DENYLIST` 二次拦截 |
| 全参数扫描 | 检查整条命令 list 中的危险 token，而非只看首个 |
| 输出截断 | 限制字节数与行数，防止内存放大 |
| 执行身份记录 | 记录 `executor_user` 写入审计 |
| 唯一出口 | 全后端 `subprocess.run` 仅出现在此文件（静态可验证） |

---

## 5. 工具体系设计

### 5.1 工具清单（16 个）

**基础感知工具（9 个，自动只读）**

| 工具名 | 功能 | 底层命令 |
| --- | --- | --- |
| `get_memory_status` | 内存状态（MB） | `free` / `/proc/meminfo` |
| `get_cpu_status` | CPU 使用率、负载、核数、Top 进程 | `/proc/stat`、`/proc/loadavg` |
| `disk_usage` | 各挂载点磁盘占用 | `df` |
| `process_list` | 按 CPU 排序的进程列表 | `ps` |
| `network_status` | 监听中的 TCP/UDP 端口 | `ss` / `netstat` |
| `get_port_usage` | 指定端口的占用进程 | `ss` / `lsof` |
| `get_service_status` | systemd 服务状态 | `systemctl` |
| `journal_query` | 系统日志查询 | `journalctl` |
| `large_file_scan` | 目录大文件扫描 | `find` |

**场景专项工具（3 个，自动只读，赛题场景点名）**

| 工具名 | 功能 | 设计要点 |
| --- | --- | --- |
| `config_drift_check` | 关键配置漂移检测 | 纯 Python 标准库（hashlib + os.stat）采集指纹，不走 Shell；10 个关键配置白名单；敏感配置内容变更定级 critical |
| `zombie_process_check` | 僵尸进程检测 | 检测 Z 状态 → 定位父进程 → 区分 init(PID 1) 自动 reap vs 服务未回收 → 给出技术正确的处置建议 |
| `disk_io_analysis` | 磁盘 I/O 瓶颈分析 | 解析 `iostat -x` 第二次采样（稳定值）；util ≥ 80% 或 await ≥ 50ms 判定瓶颈；宽松列名映射兼容不同 iostat 版本 |

**安全清理工具（4 个：2 个自动只读 + 2 个需确认）**

| 工具名 | 功能 | 权限 |
| --- | --- | --- |
| `safe_cleanup_scan` | 临时目录白名单扫描（不改文件） | 自动只读 |
| `safe_cleanup_plan` | 生成哈希绑定的 dry-run 清理计划 | 自动只读 |
| `safe_cleanup_quarantine` | 同文件系统可恢复隔离 | **需人工确认** |
| `safe_cleanup_restore` | 从隔离清单恢复文件 | **需人工确认** |

### 5.2 工具契约

所有工具遵循统一契约：

```python
@dataclass
class ToolSchema:
    name: str            # 工具唯一名
    description: str     # MCP 可发现描述
    input_schema: dict   # JSON Schema 参数定义

@dataclass
class ToolResult:
    tool: str
    status: str          # success | command_failed | no_output
                         # | parse_warning | capability_missing
    data: Any            # 结构化数据
    raw_output: str      # 原始输出
    error: str
    audit: dict          # 实际命令、执行用户、耗时、返回码
```

**`capability_missing` 状态的设计意义**：当运行环境缺少某个 Linux 命令（如 Windows 开发机没有 `iostat`），工具返回 `capability_missing` 而非抛异常，系统据此给出"环境能力受限，非安全链路失败"的明确提示。这使得同一套代码在开发机与麒麟目标机上行为可预测。

---

## 6. 智能化根因分析设计

这是赛题功能完整性评分项 4 的核心，采用**两级分析**架构。

### 6.1 第一级：单工具诊断（RecommendationEngine）

每个工具结果独立解析 → 结构化诊断：

```json
{
  "summary": "诊断结论摘要",
  "severity": "critical | warning | info | unknown",
  "findings": ["发现 1", "发现 2"],
  "recommendations": ["建议 1"],
  "next_actions": ["下一步动作"],
  "evidence": [{"tool": "...", "metric": "...", "value": "..."}]
}
```

### 6.2 第二级：跨工具根因关联（RootCauseEngine）

**这是与"逐工具解析"的本质区别**：把多个工具的证据关联起来，形成因果链。

**根因链数据结构**：

```json
{
  "chain_id": "disk_pressure_with_large_files",
  "symptom": "磁盘空间压力（/var）",
  "severity": "warning",
  "root_cause": "根因描述",
  "confidence": 0.85,
  "evidence": [{"tool": "...", "metric": "...", "value": "..."}],
  "affected_components": ["/var", "nginx"],
  "safety_assessment": {
    "critical_files_detected": true,
    "database_logs_detected": true,
    "cleanable_files": 3,
    "protected_files": 2,
    "database_files": ["/var/lib/mysql/ibdata1"],
    "notes": "数据库文件自动排除清理"
  },
  "recommendations": ["..."],
  "next_actions": ["..."]
}
```

**五个跨工具探测器**：

| 探测器 | 关联工具 | 推断逻辑 | 置信度 |
| --- | --- | --- | --- |
| `disk_pressure_with_large_files` | `disk_usage` + `large_file_scan` | 挂载点压力 ≥85% + 大文件列表 → 分类每个文件 → 区分可清理/受保护 | 0.85 |
| `cpu_pressure_with_process` | `get_cpu_status` + `process_list` | CPU ≥85% + Top 进程 ≥50% → 定位主因进程 | 0.6~0.8 |
| `memory_pressure_with_process` | `get_memory_status` + `process_list` | 内存 ≥85% + Top 内存进程 → 疑似泄漏 | 0.55~0.75 |
| `service_failure_with_journal` | `get_service_status` + `journal_query` | 服务 failed + 日志 critical/error 计数 → 崩溃线索 | 0.5~0.9 |
| `disk_pressure_with_journal` | `disk_usage` + `journal_query` + `large_file_scan` | 磁盘压力 + 日志异常服务 + 文件路径服务名 → **三方交叉验证** | 0.6~0.8 |

**设计约束**：每个探测器最多贡献一条根因链，输出按置信度降序排列。这保证结论可解释而不是噪声堆砌。

### 6.3 关键数据库文件保护（赛题点名能力）

`classify_large_file()` 对每个大文件四分类：

| 分类 | 判定依据 | `safe_to_clean` | 处置 |
| --- | --- | --- | --- |
| `database` | 扩展名（`.db`/`.ibd`/`.wal`/`.myd` 等 12 种）或路径含数据库标识（`mysql`/`postgres`/`opengauss`/`redis` 等 15 种） | **false** | 自动排除清理，需人工评估 |
| `application_log` | 扩展名 `.log`/`.out`/`.err`/`.nohup` | true | 可纳入 dry-run 计划 |
| `temporary` | 路径位于 `/tmp/`、`/var/tmp/`、`/var/cache/` 等 | true | 可纳入 dry-run 计划 |
| `unknown` | 以上都不匹配 | **false** | **默认保护**，需人工确认 |

> **设计要点**：未知归属默认保护（fail-safe），而非默认可删（fail-open）。这是安全系统的基本原则。

### 6.4 场景 A 完整链路示例

```
用户："/var 满了，帮我清理系统垃圾"
  │
  ├─ Guardrail 预检：无危险命令 token，放行
  │
  ├─ 规划器输出 tool_plan：
  │     [disk_usage, large_file_scan, journal_query]
  │
  ├─ 逐工具执行（全部只读）：
  │     disk_usage       → /var 使用率 92%
  │     large_file_scan  → 5 个大文件
  │     journal_query    → nginx 错误日志 37 条
  │
  ├─ RootCauseEngine 关联：
  │     探测器 1（disk + files）触发：
  │       ├─ /var/log/nginx/access.log  → application_log → 可清理
  │       ├─ /var/log/nginx/error.log   → application_log → 可清理
  │       ├─ /var/lib/mysql/ibdata1     → database → ❌ 受保护
  │       ├─ /var/lib/mysql/binlog.001  → database → ❌ 受保护
  │       └─ /tmp/core.12345            → temporary → 可清理
  │     探测器 5（disk + journal + files）触发：
  │       └─ nginx 日志暴涨与磁盘压力交叉验证成立
  │
  └─ 输出：
        根因链 1（置信度 0.85）：/var 磁盘压力，5 个大文件候选，
                  3 个可清理，2 个受保护；已识别 2 个关键数据库文件并自动排除
        根因链 2（置信度 0.80）：磁盘压力伴随 nginx 服务异常日志，
                  疑似 nginx 日志暴涨导致空间耗尽
        建议：对可清理项生成 safe_cleanup_plan（dry-run），
              检查 nginx 日志轮转配置
        下一步：调用 safe_cleanup_plan，逐项核对后人工确认隔离
```

**这条链路证明的能力**：不是"列出大文件"，而是"理解哪些能删、哪些绝不能碰、为什么磁盘会满、下一步怎么安全处理"。

---

## 7. 模型适配层设计

### 7.1 五种运行模式

| `MODEL_PROVIDER` | 厂商 | 默认 API Base | 用途 |
| --- | --- | --- | --- |
| `deepseek` | DeepSeek | `https://api.deepseek.com` | 国产模型主推 |
| `qwen` | 阿里千问 | DashScope 兼容端点 | 国产模型备选 |
| `kimi` | 月之暗面 | Moonshot 兼容端点 | 国产模型备选 |
| `custom` | 自定义 | 用户指定 | 私有化 OpenAI 兼容服务 |
| `offline_safe` | 内置 | 无 | 离线安全规划器，无网络依赖 |

### 7.2 安全降级链

```
配置解析 → 模型调用 → JSON 解析 → Schema 校验 → tool_plan
    │           │           │            │
    │缺Key      │超时/错误  │非法JSON    │字段不符
    ▼           ▼           ▼            ▼
  ┌──────────────────────────────────────┐
  │      降级到 offline_safe 规划器       │
  │   （绝不放宽安全策略，绝不直接执行）  │
  └──────────────────────────────────────┘
```

### 7.3 API Key 保护

| 保护措施 | 实现 |
| --- | --- |
| 注入方式 | 仅环境变量，不读取配置文件 |
| 响应过滤 | `public_metadata()` 只暴露 provider / vendor / model_name |
| 异常过滤 | 异常信息不携带 Key |
| 审计过滤 | Trace 记录 planner_source，不记录凭据 |
| 兼容变量 | `MODEL_API_KEY` > `DEEPSEEK_API_KEY`/`DASHSCOPE_API_KEY`/`MOONSHOT_API_KEY` > 旧 `LLM_API_KEY` |

---

## 8. MCP 协议设计

### 8.1 双层结构

| 层 | 实现 | 依赖 |
| --- | --- | --- |
| 协议映射层 | `backend/mcp_adapter.py` | 纯 Python，**不依赖 MCP SDK** |
| 传输层 | `backend/mcp_server.py` | stdio / SSE，依赖 MCP SDK（可选安装） |

**分层理由**：协议映射逻辑可独立测试（`test_mcp_adapter.py` 无需安装 SDK 即可验证工具发现与调用映射），传输层作为可选组件，麒麟低资源环境可跳过 SDK 安装而不影响主服务。

### 8.2 两种传输方式

| 传输 | 启动方式 | 路由 | 适用场景 |
| --- | --- | --- | --- |
| stdio | `python -m backend.mcp_server` | — | 本地 MCP 客户端（Claude Desktop 等） |
| SSE / Streamable HTTP | 随 FastAPI 自动挂载 | `/mcp/sse`、`/mcp/messages/` | 远程 MCP 客户端、Web 集成 |

**SSE 挂载设计**：

```python
try:
    from backend.mcp_server import mount_sse_server
    mount_sse_server(app)
except Exception:
    # MCP SDK 未安装：SSE 不可用，stdio 仍可用，主服务完全不受影响
    pass
```

这样 HTTP API、Vue 控制台、MCP SSE 三者同源托管在同一个端口。挂载助手只接受已注册 SafeOpsAgent 认证中间件的父应用；MCP 子应用还会校验父应用写入的认证上下文，直接启动时失败关闭。

### 8.3 安全链路复用

MCP 调用**不绕过**任何安全环节：

```
MCP tools/call
   → Registry Schema 校验
   → Guardrail 检查
   → RiskScorer 评分
   → SafeExecutor 执行
   → Audit Trace 写入
```

中风险工具通过 MCP 调用同样返回 confirm + dry-run，高危请求同样拒绝。

---

## 9. 审计设计

### 9.1 Trace v2 事件链

每次 `/chat` 请求记录 9 个阶段事件：

| 序号 | 阶段 | 记录内容 |
| --- | --- | --- |
| 1 | `receive_input` | 用户原始输入（截断） |
| 2 | `session_lifecycle` | 会话过期/重置事件（如有） |
| 3 | `precheck` | 风险分、命中规则 |
| 4 | `agent_planning` | 运行模式、模型提供方、模型名、规划来源、意图、置信度 |
| 5 | `tool_plan_created` | 规划的工具列表与参数 |
| 6 | `risk_scored` | 风险分、等级、风险因子 |
| 7 | `security_decision` | 安全决策、执行状态、决策原因 |
| 8 | `tool_executed` | 已执行工具、被阻断工具、环境提示 |
| 9 | `result_summarized` / `audit_saved` | 结论摘要、诊断严重度、证据 |

### 9.2 存储设计

| 特性 | 设计 |
| --- | --- |
| 存储引擎 | SQLite（零外部依赖，适配离线麒麟） |
| 分表策略 | 按日分表 `audit_YYYYMMDD` |
| 写入模式 | append-only，`/audit/clear` 明确返回不可清除 |
| 并发控制 | 进程内 `threading.Lock` + 每次调用独立连接 |
| 向后兼容 | `_ensure_v2_columns` 自动补列，旧库可平滑升级 |
| 内容约束 | 只记录决策摘要与事件链，**不记录模型思维链原文**，不记录凭据 |

### 9.3 可回放接口

```bash
# 列表查询
GET /audit/logs?session_id=xxx&limit=20

# 单次请求完整回放
GET /audit/trace/{request_id}
→ { found, audit（审计行）, trace（事件链）, timeline（6 步可视化时间线） }
```

---

## 10. 前端控制台设计

### 10.1 技术选型

| 项 | 选择 | 理由 |
| --- | --- | --- |
| 框架 | Vue 3 + TypeScript | 生态成熟，构建产物纯静态 |
| UI 库 | Naive UI | 深色主题适配运维场景 |
| 托管方式 | FastAPI 同源托管 `/console/` | **运行时不需要 Node.js**，适配麒麟离线部署 |
| 路由 | SPA + 后端 fallback | fallback 严格限定 `/console/` 前缀，不吞掉 API 路由 |

### 10.2 五视图设计

| 视图 | 路由 | 核心内容 |
| --- | --- | --- |
| 工作台 | `/console/` | Agent 状态、运行模式、模型提供方、工具数、安全链路图 |
| 智能诊断 | `/console/diagnosis` | 自然语言输入、工具规划卡片、诊断结论、**根因链展示** |
| 安全中心 | `/console/security` | 危险场景演示、拦截结果、风险分与命中规则可视化 |
| 工具能力 | `/console/tools` | 16 个工具分类展示、参数 Schema、只读/需确认标注 |
| 审计追踪 | `/console/audit` | 审计列表、request_id 检索、6 步时间线回放 |

### 10.3 根因链展示设计

智能诊断页在"诊断依据"区块后新增"智能化根因分析"区，每条根因链渲染为独立卡片：

```
┌────────────────────────────────────────────┐
│ 症状：磁盘空间压力（/var）    [置信度 85%]  │
│ ─────────────────────────────────────────  │
│ 根因：/var 磁盘空间紧张，扫描发现 5 个大文件 │
│      候选；其中 3 个可纳入安全清理，2 个受   │
│      保护；已识别 2 个关键数据库文件并自动   │
│      排除清理                               │
│ ─────────────────────────────────────────  │
│ 🛡 安全评估                                 │
│   检测到关键数据库文件：是                  │
│   可清理 3 个 / 受保护 2 个                 │
│   受保护文件：/var/lib/mysql/ibdata1 ...   │
│ ─────────────────────────────────────────  │
│ 影响组件：/var、nginx、mysql                │
│ 建议：对可清理项生成 dry-run 计划…          │
└────────────────────────────────────────────┘
```

---

## 11. 部署设计

### 11.1 依赖分层

| 依赖文件 | 包数 | 用途 |
| --- | --- | --- |
| `requirements-kylin.txt` | 5 | **麒麟默认部署**：fastapi、uvicorn、starlette、pydantic、httpx |
| `requirements.txt` | 6 | 完整开发环境（含 Streamlit 备用前端） |
| `requirements-dev.txt` | 1 | 自动化测试（pytest） |
| `requirements-mcp.txt` | 1 | MCP SDK（可选，仅 MCP 传输需要） |

**设计意图**：麒麟目标环境只需 5 个包即可运行完整功能，不需要 Node.js、Streamlit、pyarrow，最大化离线部署成功率。

### 11.2 服务设计

| 服务 | 状态 | 说明 |
| --- | --- | --- |
| `safeops-agent.service` | **默认启用** | FastAPI 主服务，托管 API + 控制台 + MCP SSE |
| `safeops-web.service` | 可选，默认不启用 | Streamlit 备用前端，仅开发调试用 |

---

## 附录 A：API 接口清单

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| GET | `/health` | 健康检查与版本 |
| GET | `/agent/status` | Agent 状态、运行模式、模型信息、工具计数 |
| GET | `/system/probe` | 运行环境能力探测 |
| GET | `/tools/list` | 工具清单与 Schema |
| POST | `/tools/call` | 直接工具调用（allow/confirm/reject 三态） |
| POST | `/tools/confirm` | 一次性令牌确认执行 |
| POST | `/chat` | 自然语言运维请求（主入口） |
| GET | `/audit/logs` | 审计列表 |
| GET | `/audit/trace/{request_id}` | 单次请求完整回放 |
| POST | `/audit/clear` | 明确返回 append-only 不可清除 |
| GET | `/console/*` | Vue 控制台（同源托管） |
| GET/POST | `/mcp/sse`、`/mcp/messages/` | MCP SSE 传输（SDK 安装后可用） |
| GET | `/docs` | OpenAPI 交互文档 |

## 附录 B：相关文档

| 文档 | 路径 |
| --- | --- |
| 需求分析报告 | `docs/requirements-analysis.md` |
| 产品说明书 | `docs/product-manual.md` |
| 功能测试报告 | `docs/test-report.md` |
| 性能测试报告 | `docs/performance-test-report.md` |
| 安全设计说明 | `docs/security-design.md` |
| MCP 工具设计 | `docs/mcp-tool-design.md` |
