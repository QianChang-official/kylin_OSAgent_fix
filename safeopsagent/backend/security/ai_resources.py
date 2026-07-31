"""Curated AI security resources used by the console and guardrail docs.

The entries intentionally store titles, categories and application notes only.
Full articles and third-party tool pages stay at their original URLs.
"""
from __future__ import annotations

from typing import Any

SOURCE_CHECKED_AT = "2026-07-30"

OPENAI_CODEX_SECURITY = {
    "id": "openai-codex-security",
    "source": "OpenAI Codex Security",
    "title": "@openai/codex-security",
    "url": "https://github.com/openai/codex-security",
    "package": "@openai/codex-security",
    "pinned_version": "0.1.4",
    "summary": (
        "OpenAI official TypeScript SDK and CLI for repository security scans. "
        "SafeOpsAgent runs the pinned package only on an authorized external scan host "
        "and imports sealed results read-only."
    ),
    "commands": [
        "cd integrations/codex-security",
        "npm ci --ignore-scripts",
        "npm run scan -- --repository /path/to/safeopsagent --output-dir /private/results/scan-id --dry-run",
    ],
    "safeops_usage": [
        "run local preflight on a supported x64/arm64 scan host without credentials",
        "scan only repositories the operator owns or is authorized to assess",
        "store reports outside the scanned repository and review before sharing",
        "import only completed, hash-verified summaries; never execute remediation text",
    ],
}


BUTIAN_AI_TOOL_CATEGORIES = [
    {
        "slug": "DYYJ",
        "name": "钓鱼邮件防御",
        "url": "https://forum.butian.net/AITools/DYYJ/newest",
        "safeops_usage": "沉淀钓鱼告警分析与邮件取证流程，不自动发送或生成钓鱼载荷。",
    },
    {
        "slug": "MCP",
        "name": "MCP安全",
        "url": "https://forum.butian.net/AITools/MCP/newest",
        "safeops_usage": "用于检查工具描述污染、越权调用、上下文投毒和 MCP 服务暴露面。",
    },
    {
        "slug": "SJYS",
        "name": "数据隐私安全",
        "url": "https://forum.butian.net/AITools/SJYS/newest",
        "safeops_usage": "映射到凭据路径保护、审计脱敏和敏感输出阻断规则。",
    },
    {
        "slug": "MXSRSC",
        "name": "模型输入输出安全",
        "url": "https://forum.butian.net/AITools/MXSRSC/newest",
        "safeops_usage": "补充提示词注入、输出投毒、隐藏 Unicode 等输入输出测试样例。",
    },
    {
        "slug": "MXLBX",
        "name": "模型鲁棒性安全",
        "url": "https://forum.butian.net/AITools/MXLBX/newest",
        "safeops_usage": "用于设计对抗样例回归集，避免正常运维请求被误杀。",
    },
    {
        "slug": "GYL",
        "name": "AI供应链安全",
        "url": "https://forum.butian.net/AITools/GYL/newest",
        "safeops_usage": "加入依赖、模型、插件、脚本来源核验和最小权限运行建议。",
    },
    {
        "slug": "AGENT",
        "name": "Agent智能体安全",
        "url": "https://forum.butian.net/AITools/AGENT/newest",
        "safeops_usage": "强化工具白名单、人工确认、会话隔离、任务链审计。",
    },
    {
        "slug": "TLHJ",
        "name": "推理环境安全",
        "url": "https://forum.butian.net/AITools/TLHJ/newest",
        "safeops_usage": "约束模型运行环境、网络访问、环境变量和扫描结果落盘位置。",
    },
    {
        "slug": "NRHG",
        "name": "内容合规安全",
        "url": "https://forum.butian.net/AITools/NRHG/newest",
        "safeops_usage": "在最终回复和报告生成阶段增加合规提示与敏感内容过滤。",
    },
    {
        "slug": "SKILL",
        "name": "Skill安全",
        "url": "https://forum.butian.net/AITools/SKILL/newest",
        "safeops_usage": "审查技能/插件清单、指令覆盖风险和第三方脚本行为。",
    },
    {
        "slug": "MXZSCQ",
        "name": "模型知识产权保护",
        "url": "https://forum.butian.net/AITools/MXZSCQ/newest",
        "safeops_usage": "避免把私有模型提示词、评测集和内部知识库泄露到报告中。",
    },
    {
        "slug": "WXJC",
        "name": "威胁检测与响应",
        "url": "https://forum.butian.net/AITools/WXJC/newest",
        "safeops_usage": "补强日志分析、指标异常、攻击链证据链和处置建议。",
    },
    {
        "slug": "LDLY",
        "name": "漏洞利用自动化",
        "url": "https://forum.butian.net/AITools/LDLY/newest",
        "safeops_usage": "仅用于授权靶场验证；SafeOpsAgent 不自动执行利用或后渗透动作。",
        "restricted": True,
    },
    {
        "slug": "YYAQ",
        "name": "应用安全测试",
        "url": "https://forum.butian.net/AITools/YYAQ/newest",
        "safeops_usage": "用于设计 Web/API 安全检查清单和只读扫描前置确认。",
    },
    {
        "slug": "XXZC",
        "name": "信息侦察自动化",
        "url": "https://forum.butian.net/AITools/XXZC/newest",
        "safeops_usage": "限制在资产归属明确的范围内，所有目标和输出进入审计。",
        "restricted": True,
    },
    {
        "slug": "WXQB",
        "name": "威胁情报分析",
        "url": "https://forum.butian.net/AITools/WXQB/newest",
        "safeops_usage": "关联 IOC、日志特征和风险分级，输出防护建议而不是攻击脚本。",
    },
    {
        "slug": "SHGC",
        "name": "社会工程学攻击",
        "url": "https://forum.butian.net/AITools/SHGC/newest",
        "safeops_usage": "仅作防御意识与检测样例，不生成欺骗投递内容。",
        "restricted": True,
    },
    {
        "slug": "EYYBFX",
        "name": "恶意样本分析",
        "url": "https://forum.butian.net/AITools/EYYBFX/newest",
        "safeops_usage": "用于隔离环境内样本元数据分析，禁止在生产主机执行样本。",
        "restricted": True,
    },
    {
        "slug": "AQYY",
        "name": "安全运营自动化",
        "url": "https://forum.butian.net/AITools/AQYY/newest",
        "safeops_usage": "沉淀告警归并、证据链、变更关联和人工确认工作流。",
    },
    {
        "slug": "EYDM",
        "name": "恶意代码生成",
        "url": "https://forum.butian.net/AITools/EYDM/newest",
        "safeops_usage": "仅用于防护边界说明和检测规则，不生成或运行恶意代码。",
        "restricted": True,
    },
]


BUTIAN_AI_SECURITY_ARTICLES = [
    {
        "id": 269,
        "title": "基于 DeepSeek 的 LLM 红队靶场设计：构建攻防训练平台时的若干工程取舍",
        "url": "https://forum.butian.net/ai_security/269",
        "topics": ["LLM红队", "靶场", "工程取舍"],
        "safeops_usage": "作为离线安全评测和演示靶场设计参考，避免在生产环境跑攻击流程。",
    },
    {
        "id": 265,
        "title": "基于 AI Agent 的自动化 API 渗透测试框架设计与实现",
        "url": "https://forum.butian.net/ai_security/265",
        "topics": ["Agent", "API安全", "授权测试"],
        "safeops_usage": "抽取授权边界、目标确认、报告留痕思路，默认不触发主动攻击。",
    },
    {
        "id": 260,
        "title": "当3+5=?成为攻击入口：MCP 工具投毒与链式滥用攻击场景复盘",
        "url": "https://forum.butian.net/ai_security/260",
        "topics": ["MCP", "工具投毒", "链式滥用"],
        "safeops_usage": "补充 MCP 工具描述可信度、参数重校验和跨工具链审计规则。",
    },
    {
        "id": 250,
        "title": "Flowise3.1.1版本深度研究：SSRF拿云账户及沙箱逃逸RCE",
        "url": "https://forum.butian.net/ai_security/250",
        "topics": ["SSRF", "沙箱逃逸", "云凭据"],
        "safeops_usage": "强化元数据服务访问限制、云凭据脱敏和外连能力最小化。",
    },
    {
        "id": 249,
        "title": "Manifest V3架构下的大模型驱动型SOC日志智能分析助手",
        "url": "https://forum.butian.net/ai_security/249",
        "topics": ["SOC", "日志分析", "浏览器扩展"],
        "safeops_usage": "参考日志智能分析助手的权限隔离与告警解释方式。",
    },
    {
        "id": 263,
        "title": "AI Agent 工具调用安全实战：从工具描述污染到越权读取的复现与防护",
        "url": "https://forum.butian.net/ai_security/263",
        "topics": ["Agent", "工具描述污染", "越权读取"],
        "safeops_usage": "映射到工具 Schema、白名单、只读边界和敏感路径阻断测试。",
    },
    {
        "id": 274,
        "title": "一句话调度全链路：重保蓝队安全助手的设计与实现",
        "url": "https://forum.butian.net/ai_security/274",
        "topics": ["蓝队", "安全助手", "调度"],
        "safeops_usage": "用于完善 SafeOpsAgent 的蓝队场景编排、证据链和建议输出。",
    },
    {
        "id": 246,
        "title": "基于 MCP的App隐私合规检测实践",
        "url": "https://forum.butian.net/ai_security/246",
        "topics": ["MCP", "隐私合规", "App检测"],
        "safeops_usage": "参考隐私合规检查项，补强数据访问、权限说明和报告模板。",
    },
    {
        "id": 237,
        "title": "我如何在本地复现 CVE-2026-31221：从 PyTorch Lightning checkpoint 加载到任意代码执行",
        "url": "https://forum.butian.net/ai_security/237",
        "topics": ["模型供应链", "反序列化", "本地复现"],
        "safeops_usage": "提醒模型与 checkpoint 文件按不可信输入处理，加载前做隔离与来源校验。",
    },
    {
        "id": 233,
        "title": "被拐的凭据：n8n 共享工作流代理劫持漏洞分析",
        "url": "https://forum.butian.net/ai_security/233",
        "topics": ["凭据", "工作流", "代理劫持"],
        "safeops_usage": "强化工作流凭据边界、代理配置审计和环境变量泄露检测。",
    },
    {
        "id": 232,
        "title": "借来的身份：n8n ExecuteWorkflow 身份别名化漏洞分析",
        "url": "https://forum.butian.net/ai_security/232",
        "topics": ["身份别名化", "工作流", "权限边界"],
        "safeops_usage": "用于检查会话身份、审计主体和跨工作流调用是否一致。",
    },
    {
        "id": 216,
        "title": "Prompt 中的不可见 Unicode 字符攻击",
        "url": "https://forum.butian.net/ai_security/216",
        "topics": ["提示词安全", "Unicode", "混淆"],
        "safeops_usage": "补充输入规范化、不可见字符检测和攻击样例回归测试。",
    },
]


PROJECT_APPLICATIONS = [
    {
        "area": "工具调用安全",
        "controls": ["工具白名单", "JSON Schema 参数校验", "敏感路径阻断", "人工确认令牌"],
        "mapped_sources": ["OpenAI Codex Security", "补天 MCP安全", "补天 Agent智能体安全"],
    },
    {
        "area": "提示词和输出安全",
        "controls": ["Unicode 规范化", "提示词注入规则", "工具输出二次扫描", "审计留痕"],
        "mapped_sources": ["补天 模型输入输出安全", "补天 Prompt 中的不可见 Unicode 字符攻击"],
    },
    {
        "area": "供应链和扫描",
        "controls": ["codex-security dry-run", "知识库扫描上下文", "结果仓库外落盘", "报告人工复核"],
        "mapped_sources": ["OpenAI Codex Security", "补天 AI供应链安全", "补天 Skill安全"],
    },
    {
        "area": "蓝队运维场景",
        "controls": ["指标异常检测", "日志分析", "变更关联", "可恢复处置"],
        "mapped_sources": ["补天 威胁检测与响应", "补天 安全运营自动化"],
    },
]


def security_resources_payload() -> dict[str, Any]:
    """Return a stable, UI-friendly resource catalog."""
    restricted_count = sum(1 for item in BUTIAN_AI_TOOL_CATEGORIES if item.get("restricted"))
    return {
        "last_checked_at": SOURCE_CHECKED_AT,
        "sources": [
            {
                "name": "OpenAI Codex Security",
                "url": "https://github.com/openai/codex-security",
                "usage": "authorized repository security scanning",
            },
            {
                "name": "补天 AI安全工具",
                "url": "https://forum.butian.net/AITools",
                "usage": "tool-category radar and defensive capability mapping",
            },
            {
                "name": "补天 AI安全技术",
                "url": "https://forum.butian.net/AISecurity",
                "usage": "article index and project hardening references",
            },
        ],
        "codex_security": OPENAI_CODEX_SECURITY,
        "tool_categories": BUTIAN_AI_TOOL_CATEGORIES,
        "articles": BUTIAN_AI_SECURITY_ARTICLES,
        "project_applications": PROJECT_APPLICATIONS,
        "policy": {
            "restricted_category_count": restricted_count,
            "summary": (
                "Offensive categories are kept as defensive references only. "
                "SafeOpsAgent will not generate, hide, or execute exploit, malware, phishing, "
                "or unauthorized reconnaissance workflows."
            ),
        },
    }
