# SafeOpsAgent AI 安全知识库

更新时间：2026-07-30

本文只保存外部资源的索引和 SafeOpsAgent 可落地的防护映射，不复制原文内容。Codex Security 扫描时可把 `docs/` 作为 `--knowledge-base`，让扫描理解项目的边界设计。

## 来源

- OpenAI Codex Security：<https://github.com/openai/codex-security>
- 补天 AI 安全工具：<https://forum.butian.net/AITools>
- 补天 AI 安全技术：<https://forum.butian.net/AISecurity>

## Codex Security 接入方式

项目通过隔离扫描主机接入 `@openai/codex-security`，生产后端不直接启动外部扫描进程。

- 扫描入口位于 `integrations/codex-security/`，用于 x64/arm64 CI worker 或独立扫描主机。
- 先执行 dry-run：`npm run scan -- --repository /path/to/safeopsagent --output-dir /private/results/scan-20260730 --dry-run`
- 真实扫描需要显式授权、受控凭据和成本上限，例如 `--auth api-key --max-cost 5`
- 扫描目标必须是非符号链接仓库目录，输出目录必须位于仓库外
- 知识库可显式传入 `docs/`，用于提供架构、安全策略和外部资源映射
- 在 SafeOpsAgent 主机上用 `CODEX_SECURITY_RESULTS_DIR` 指向仓库外的私有结果父目录；控制台只读取通过路径、大小、结构和 SHA-256 校验的摘要

真实扫描可能读取仓库内容并使用外部认证。只扫描自己拥有或被授权评估的仓库，报告目录应放在仓库外并限制访问。SafeOpsAgent 只导入完成后、哈希校验通过的 JSON 摘要，不执行报告里的修复建议。

这里的 SHA-256 校验只证明 manifest 声明与结果文件一致，不证明结果一定来自某台扫描节点。结果目录 ACL 是当前信任根：仅允许受信扫描流水线写入，并由人工复核摘要。

## 补天 AI 安全工具映射

可直接用于项目防护能力建设的类别：

- MCP 安全：工具描述污染、越权调用、上下文投毒、MCP 服务暴露面
- 数据隐私安全：凭据路径保护、敏感输出阻断、审计脱敏
- 模型输入输出安全：提示词注入、输出投毒、隐藏 Unicode 回归样例
- Agent 智能体安全：工具白名单、人工确认、会话隔离、任务链审计
- 推理环境安全：运行环境、网络访问、环境变量和扫描结果目录约束
- Skill 安全：技能/插件清单审查、指令覆盖风险、第三方脚本行为审计
- 威胁检测与响应：日志分析、指标异常、攻击链证据和处置建议
- 安全运营自动化：告警归并、证据链、变更关联、可恢复处置

只作为防御参考的类别：

- 漏洞利用自动化
- 信息侦察自动化
- 社会工程学攻击
- 恶意样本分析
- 恶意代码生成

SafeOpsAgent 不生成、隐藏或执行利用载荷、恶意代码、钓鱼内容、未授权侦察或后渗透流程。

## 补天 AI 安全技术映射

- MCP 工具投毒与链式滥用：补强 MCP 工具描述可信度、参数重校验、跨工具链审计
- AI Agent 工具调用安全：补强工具 Schema、白名单、只读边界和敏感路径阻断
- Prompt 中的不可见 Unicode 字符攻击：补强输入规范化、不可见字符检测和回归测试
- AI Agent 自动化 API 测试框架：只提取授权边界、目标确认和报告留痕，不触发主动攻击
- Flowise SSRF 与沙箱逃逸研究：补强外连限制、元数据服务防护、云凭据脱敏
- PyTorch Lightning checkpoint 任意代码执行复现：将模型与 checkpoint 文件视为不可信输入
- n8n 工作流代理和身份问题：检查会话身份、审计主体、环境变量与凭据边界
- 蓝队安全助手设计：补强指标异常检测、日志解释、变更关联和处置建议

## 当前项目落点

- `backend/security/guardrail.py`：提示词注入、危险命令、敏感路径、隐藏字符规范化
- `backend/tools/registry.py`：工具白名单和 JSON Schema 参数校验
- `backend/app.py`：工具调用二次校验、人工确认、审计记录和资源 API
- `backend/security/console_auth.py`：真实服务端登录、签名会话、HttpOnly Cookie、CSRF 和失败限流；不存在隐藏入口或前端绕过
- `backend/security_intel/`：精选工具登记表，以及按不可信内容处理的公开 AISecurity RSS 快照与确定性防护映射
- `integrations/codex-security/scan.mjs`：隔离扫描主机上的 Codex Security runner
- `backend/security/codex_results.py`：完成扫描结果的哈希校验与只读摘要导入
- `frontend/vue-console/src/views/SecurityView.vue`：安全验证场景、外部资源索引、项目落地说明

## 评测建议

1. 在隔离扫描主机使用 `integrations/codex-security/` 的 dry-run 验证环境、授权和输出路径。
2. 用 `scripts/run_security_benchmark.py` 运行项目内安全回归样例。
3. 针对 MCP 工具污染、隐藏 Unicode、凭据路径读取、工具输出注入补充测试样例。
4. 对真实扫描结果进行人工复核，不把报告作为自动修复或自动阻断的唯一依据。
