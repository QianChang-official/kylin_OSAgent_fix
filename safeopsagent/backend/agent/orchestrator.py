"""Agent orchestrator: guarded planning, read-only tool execution, and audit."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List

from backend import config
from backend.analysis import build_diagnosis
from backend.audit.logger import get_logger
from backend.llm.deepseek_client import DeepSeekClient
from backend.security.guardrail import Guardrail, SecurityCheck
from backend.security.rule_labels import flatten_rule_hits, label_rules
from backend.tools.registry import ToolResult, get_registry


CHAT_READONLY_TOOLS = {
    "get_memory_status",
    "disk_usage",
    "process_list",
    "network_status",
    "get_port_usage",
    "get_service_status",
    "journal_query",
    "large_file_scan",
    "get_cpu_status",
    "safe_cleanup_scan",
    "safe_cleanup_plan",
    "config_drift_check",
    "zombie_process_check",
    "disk_io_analysis",
    "impact_analysis",
}
MAX_CHAT_TOOL_PLAN = 3
ENVIRONMENT_LIMITED_MESSAGE = "当前环境缺少对应 Linux 命令，建议在银河麒麟、Linux 或 WSL 中完整验证。"
MODEL_VENDOR_LABELS = {
    "deepseek": "DeepSeek",
    "qwen": "千问",
    "kimi": "Kimi",
    "custom": "自定义模型服务",
    "offline_safe": "内置安全规划器",
}


class AgentOrchestrator:
    def __init__(self):
        self.llm = DeepSeekClient()
        self.guardrail = Guardrail()
        self.registry = get_registry()
        self.audit = get_logger()
        self._sessions: Dict[str, List[Dict]] = {}
        self._session_meta: Dict[str, Dict[str, float]] = {}

    def run(self, session_id: str, user_input: str) -> Dict[str, Any]:
        now = time.time()
        start_ms = int(now * 1000)
        request_id = str(uuid.uuid4())[:8]

        input_check = self.guardrail.check_input(user_input)
        risk_assessment = self.guardrail.score_100(input_check=input_check)
        context, session_events = self._load_session_context(session_id, now)

        result = self._base_result(request_id, user_input, session_events, risk_assessment, input_check)

        # High-risk input is stopped before any model call or tool call.
        if risk_assessment.security_decision != "allow":
            result.update({
                "selected_tool": "none",
                "execution_status": "blocked",
                "security_reason": "blocked_by_precheck",
                "summary": "系统已拒绝该高风险请求，未执行任何系统命令。",
                "analysis": "本地安全护栏在调用模型前命中了高风险规则。",
                "next_step": "可查看审计 Trace 获取命中规则；如需只读排查，请改为查询内存、端口、服务或日志状态。",
                "response": "请求涉及高危操作，系统已阻止执行。",
                "suggestion": self.guardrail.suggest_alternative(5, user_input),
            })
            self._log(session_id, request_id, user_input, result, start_ms)
            return result

        tools = self.registry.list_tools()
        llm_result = self.llm.chat(
            messages=context + [{"role": "user", "content": user_input}],
            tools=tools,
        )
        self._apply_planner_metadata(result, llm_result)

        planned_tools = self._extract_tool_plan(llm_result)
        result["tool_plan"] = planned_tools

        if not planned_tools:
            self._apply_no_action(result)
            self._log(session_id, request_id, user_input, result, start_ms)
            return result

        plan_result = self._execute_tool_plan(input_check, tools, planned_tools)
        result.update(plan_result)
        self._apply_diagnosis(result)

        if result["tool_plan"]:
            first_tool = result["tool_plan"][0]
            result["selected_tool"] = first_tool.get("tool_name", "none")
            result["tool_arguments"] = first_tool.get("arguments", {})
        if result["tool_results"]:
            first_result = result["tool_results"][0]
            result["tool_result"] = {
                "tool": first_result.get("tool"),
                "status": first_result.get("status"),
                "data": first_result.get("data"),
            }

        result["response"] = result["summary"]

        context.append({"role": "user", "content": user_input})
        context.append({"role": "assistant", "content": result["response"]})
        self._sessions[session_id] = self._trim_context(context)

        self._log(session_id, request_id, user_input, result, start_ms)
        return result

    def _base_result(self, request_id: str, user_input: str, session_events: list[str],
                     risk_assessment, input_check: SecurityCheck) -> dict:
        return {
            "request_id": request_id,
            "user_input": user_input,
            "session_events": session_events,
            "risk_level": risk_assessment.risk_level,
            "legacy_risk_level": risk_assessment.legacy_risk_level,
            "risk_score": risk_assessment.score,
            "risk_band": risk_assessment.band,
            "risk_factors": risk_assessment.factors,
            "matched_rules": risk_assessment.matched_rules,
            "rule_labels": [],
            "security_decision": risk_assessment.security_decision,
            "security_reason": "",
            "rule_hits": list(input_check.rule_hits),
            "executed": False,
            "selected_tool": "",
            "tool_arguments": {},
            "tool_audit": {},
            "tool_result": None,
            "tool_results": [],
            "response": "",
            "suggestion": None,
            "agent_mode": "offline_safe",
            "model_provider": "offline_safe",
            "model_vendor": "内置安全规划器",
            "planner_source": "offline_safe",
            "model_name": "offline",
            "intent": "",
            "planner_confidence": 0.0,
            "planner_explanation": "",
            "tool_plan": [],
            "execution_status": "not_executed",
            "environment_message": "",
            "summary": "",
            "analysis": "",
            "next_step": "",
            "diagnosis": {
                "summary": "",
                "severity": "unknown",
                "findings": [],
                "recommendations": [],
                "next_actions": [],
                "evidence": [],
            },
        }

    def _apply_planner_metadata(self, result: dict, llm_result: dict) -> None:
        agent_mode = str(llm_result.get("agent_mode", "offline_safe"))
        if agent_mode != "model_api":
            agent_mode = "offline_safe"
        provider = str(llm_result.get("model_provider", "")).lower()
        if agent_mode == "offline_safe":
            provider = "offline_safe"
        elif provider not in {"deepseek", "qwen", "kimi", "custom"}:
            provider = "custom"

        result["agent_mode"] = agent_mode
        result["model_provider"] = provider
        result["model_vendor"] = MODEL_VENDOR_LABELS[provider]
        result["planner_source"] = (
            "domestic_model" if agent_mode == "model_api" else "offline_safe"
        )
        result["model_name"] = (
            str(llm_result.get("model_name", ""))[:200]
            if agent_mode == "model_api"
            else "offline"
        )
        result["intent"] = str(llm_result.get("intent", ""))[:200]
        result["planner_confidence"] = self._safe_float(
            llm_result.get("planner_confidence", llm_result.get("confidence", 0.0))
        )
        result["planner_explanation"] = str(
            llm_result.get(
                "planner_explanation",
                llm_result.get("explanation", llm_result.get("reason", "")),
            )
        )[:500]
        if llm_result.get("fallback_reason"):
            result["fallback_reason"] = llm_result.get("fallback_reason")

    def _apply_no_action(self, result: dict) -> None:
        result.update({
            "selected_tool": "none",
            "tool_arguments": {},
            "risk_score": 0,
            "risk_level": "low",
            "risk_band": "low",
            "legacy_risk_level": 1,
            "risk_factors": [],
            "matched_rules": [],
            "security_decision": "no_action",
            "security_reason": "no_executable_tool",
            "execution_status": "not_executed",
            "summary": "暂未识别到可执行的安全运维任务。",
            "analysis": "模型或离线规划器没有给出可执行的白名单只读工具。",
            "next_step": "请换一种方式描述要检查的系统问题，例如：查看内存状态、检查端口占用、查询服务日志。",
            "response": "暂未识别到可执行的安全运维任务。请补充要检查的对象，例如：查看内存状态、检查端口占用、查询服务日志。",
        })

    def _extract_tool_plan(self, llm_result: dict) -> list[dict]:
        raw_plan = llm_result.get("tool_plan")
        if raw_plan is None:
            tool_name = llm_result.get("tool", llm_result.get("tool_name", "none"))
            if self._is_no_action_tool(tool_name):
                return []
            raw_plan = [{
                "tool_name": tool_name,
                "arguments": llm_result.get("args", llm_result.get("arguments", {})),
                "reason": llm_result.get("reason", ""),
            }]
        elif isinstance(raw_plan, dict):
            raw_plan = [raw_plan]
        elif not isinstance(raw_plan, list):
            return []

        normalized = []
        for item in raw_plan[:MAX_CHAT_TOOL_PLAN]:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name", item.get("tool", "none")) or "").strip()
            if self._is_no_action_tool(tool_name):
                continue
            arguments = item.get("arguments", item.get("args", {}))
            if not isinstance(arguments, dict):
                arguments = {}
            normalized.append({
                "tool_name": tool_name,
                "display_name": self._display_name(tool_name),
                "arguments": arguments,
                "reason": str(item.get("reason", ""))[:300],
                "status": "planned",
                "risk_score": None,
            })
        return normalized

    def _execute_tool_plan(self, input_check: SecurityCheck, tools: list[dict], planned_tools: list[dict]) -> dict:
        available_tools = [tool["name"] for tool in tools]
        tool_results = []
        rule_hits = list(input_check.rule_hits)
        matched_rules = list(input_check.rule_hits)
        risk_factors = []
        risk_score = 10
        risk_level = "low"
        legacy_risk_level = 1
        tool_audit = {}
        any_success = False
        any_called = False
        any_blocked = False
        any_failed = False
        environment_limited = False

        for entry in planned_tools:
            tool_name = entry["tool_name"]
            arguments = entry.get("arguments", {})

            if tool_name not in CHAT_READONLY_TOOLS:
                entry.update({
                    "status": "blocked",
                    "error": "Tool is not approved for automatic /chat execution.",
                    "security_decision": "reject",
                    "risk_score": 100,
                })
                any_blocked = True
                matched_rules.append(f"chat_non_readonly_tool:{tool_name}")
                risk_factors.append(f"blocked_tool:{tool_name}")
                risk_score = max(risk_score, 100)
                continue

            schema_ok, schema_error = self.registry.validate_args(tool_name, arguments)
            if not schema_ok:
                entry.update({
                    "status": "blocked",
                    "error": schema_error,
                    "security_decision": "reject",
                    "risk_score": 100,
                })
                any_blocked = True
                matched_rules.append(f"schema_validation:{tool_name}")
                risk_factors.append(f"schema_validation:{tool_name}")
                risk_score = max(risk_score, 100)
                continue

            tool_check = self.guardrail.validate_tool_selection(tool_name, available_tools)
            arg_check = self.guardrail.validate_tool_args(tool_name, arguments)
            assessment = self.guardrail.score_100(
                input_check=input_check,
                tool_check=tool_check,
                arg_check=arg_check,
                tool_name=tool_name,
                arguments=arguments,
            )
            entry.update({
                "risk_score": assessment.score,
                "risk_level": assessment.risk_level,
                "security_decision": assessment.security_decision,
            })
            rule_hits.extend(tool_check.rule_hits)
            rule_hits.extend(arg_check.rule_hits)
            matched_rules.extend(assessment.matched_rules)
            risk_factors.extend(assessment.factors)
            risk_score = max(risk_score, assessment.score)
            risk_level = self._max_risk_level(risk_level, assessment.risk_level)
            legacy_risk_level = max(legacy_risk_level, assessment.legacy_risk_level)

            if assessment.security_decision != "allow":
                entry.update({
                    "status": "blocked",
                    "error": "Tool plan blocked by risk scorer.",
                })
                any_blocked = True
                continue

            try:
                tool_result = self.registry.call(tool_name, arguments)
                any_called = True
            except Exception as exc:
                entry.update({
                    "status": "failed",
                    "error": str(exc),
                })
                any_failed = True
                continue

            output_payload = self._tool_result_payload(tool_result)
            output_text = tool_result.raw_output or json.dumps(output_payload, ensure_ascii=False, default=str)
            output_check = self.guardrail.check_tool_output(output_text)
            output_assessment = self.guardrail.score_100(
                input_check=input_check,
                tool_check=tool_check,
                arg_check=arg_check,
                output_check=output_check,
                tool_name=tool_name,
                arguments=arguments,
            )
            rule_hits.extend(output_check.rule_hits)
            matched_rules.extend(output_assessment.matched_rules)
            risk_factors.extend(output_assessment.factors)
            risk_score = max(risk_score, output_assessment.score)
            risk_level = self._max_risk_level(risk_level, output_assessment.risk_level)
            legacy_risk_level = max(legacy_risk_level, output_assessment.legacy_risk_level)

            if not output_check.passed:
                entry.update({
                    "status": "blocked",
                    "error": "Tool output blocked by guardrail.",
                    "security_decision": "reject",
                    "risk_score": output_assessment.score,
                })
                any_blocked = True
                continue

            output_payload["arguments"] = arguments
            tool_results.append(output_payload)
            entry.update({
                "status": tool_result.status,
                "result_status": tool_result.status,
                "error": tool_result.error,
                "data_preview": self._preview(tool_result.data),
            })
            if tool_result.audit and not tool_audit:
                tool_audit = tool_result.audit
            if tool_result.status == "success":
                any_success = True
            elif tool_result.status == "capability_missing":
                environment_limited = True
            else:
                any_failed = True

        execution_status = self._execution_status(
            any_success=any_success,
            any_called=any_called,
            any_blocked=any_blocked,
            any_failed=any_failed,
            environment_limited=environment_limited,
        )
        security_decision = self._chat_security_decision(execution_status, risk_score)
        summary, analysis, next_step = self._summarize_plan(planned_tools, tool_results, execution_status)
        environment_message = ENVIRONMENT_LIMITED_MESSAGE if environment_limited else ""

        return {
            "tool_plan": planned_tools,
            "tool_results": tool_results,
            "tool_audit": tool_audit,
            "rule_hits": self._dedupe(rule_hits),
            "matched_rules": self._dedupe(matched_rules),
            "risk_factors": self._dedupe(risk_factors),
            "risk_score": min(100, risk_score),
            "risk_level": self._risk_level_from_score(risk_score) if risk_score >= 100 else risk_level,
            "risk_band": self._risk_level_from_score(risk_score) if risk_score >= 100 else risk_level,
            "legacy_risk_level": 5 if risk_score >= 100 else legacy_risk_level,
            "security_decision": security_decision,
            "security_reason": f"chat_plan_{execution_status}",
            "execution_status": execution_status,
            "environment_message": environment_message,
            "executed": any_success,
            "summary": summary,
            "analysis": analysis,
            "next_step": next_step,
        }

    def _execution_status(self, *, any_success: bool, any_called: bool, any_blocked: bool,
                          any_failed: bool, environment_limited: bool) -> str:
        if any_success and (any_blocked or any_failed or environment_limited):
            return "partial"
        if any_success:
            return "success"
        if any_blocked and not any_called:
            return "blocked"
        if environment_limited:
            return "environment_limited"
        if any_failed:
            return "failed"
        return "not_executed"

    def _chat_security_decision(self, execution_status: str, risk_score: int) -> str:
        if risk_score >= 100 and execution_status in {"blocked", "not_executed", "failed"}:
            return "failed" if execution_status == "failed" else "reject"
        if execution_status == "partial":
            return "partial"
        if execution_status in {"failed", "environment_limited"}:
            return "failed"
        if execution_status in {"blocked", "not_executed"}:
            return "no_action"
        return "allow"

    def _summarize_plan(self, plan: list[dict], results: list[dict], status: str) -> tuple[str, str, str]:
        successful = [item["tool_name"] for item in plan if item.get("status") == "success"]
        blocked = [item["tool_name"] for item in plan if item.get("status") == "blocked"]
        failed = [item["tool_name"] for item in plan if item.get("status") not in {"success", "planned", "blocked"}]
        if status == "success":
            tools_text = "、".join(successful)
            return (
                f"已完成只读运维检查：{tools_text}。",
                "系统仅调用了白名单只读工具，没有修改系统配置或执行破坏性命令。",
                "如仍需继续排查，可进一步查看进程、端口、服务状态或相关日志。",
            )
        if status == "partial":
            return (
                "已完成部分只读检查，部分工具因环境能力、参数或安全规则未执行。",
                f"成功工具：{', '.join(successful) or '无'}；受阻工具：{', '.join(blocked + failed) or '无'}。",
                "建议先根据已返回结果判断方向，再在 Linux、WSL 或银河麒麟环境补充验证缺失工具。",
            )
        if status == "environment_limited":
            return (
                "当前环境缺少对应 Linux 运维命令，工具无法完成。",
                "这通常表示运行环境能力不足，不代表 SafeOpsAgent 安全链路失败。",
                "建议在银河麒麟、Linux 或 WSL 环境下进行完整验证。",
            )
        if status == "blocked":
            return (
                "工具规划已被安全链路阻止，未执行系统命令。",
                f"受阻工具：{', '.join(blocked) or '无'}。",
                "请检查输入参数或改为明确的只读运维查询。",
            )
        if status == "failed":
            return (
                "工具调用未能成功完成，系统未获得有效检查结果。",
                f"失败工具：{', '.join(blocked + failed) or '无'}。",
                "请查看错误信息，或在完整 Linux / Kylin 环境下重试。",
            )
        return (
            "暂未执行任何系统工具。",
            "当前请求没有形成可执行的白名单只读工具计划。",
            "请补充要检查的对象，例如内存、磁盘、端口、服务或日志。",
        )

    def _tool_result_payload(self, tool_result: ToolResult) -> dict:
        return {
            "tool": tool_result.tool,
            "status": tool_result.status,
            "data": tool_result.data,
            "raw_output": tool_result.raw_output,
            "error": tool_result.error,
        }

    def _display_name(self, tool_name: str) -> str:
        schema = self.registry.get_schema(tool_name)
        return schema.description if schema else tool_name

    def _safe_float(self, value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, numeric))

    def _preview(self, value: Any, limit: int = 300) -> str:
        text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
        return text[:limit] + ("...[truncated]" if len(text) > limit else "")

    def _max_risk_level(self, current: str, incoming: str) -> str:
        order = {"low": 1, "medium": 2, "high": 3, "forbidden": 4}
        return incoming if order.get(incoming, 1) > order.get(current, 1) else current

    def _risk_level_from_score(self, score: int) -> str:
        if score >= 100:
            return "forbidden"
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _dedupe(self, values: list) -> list:
        return list(dict.fromkeys(values))

    def _build_agent_trace(self, session_id: str, request_id: str, user_input: str, result: dict) -> dict:
        events = [
            {"stage": "receive_input", "summary": user_input[:500]},
        ]
        if result.get("session_events"):
            events.append({
                "stage": "session_lifecycle",
                "events": result.get("session_events", [])[:20],
            })
        events.extend([
                {"stage": "precheck", "risk_score": result.get("risk_score"), "matched_rules": result.get("matched_rules", [])[:20]},
                {
                    "stage": "agent_planning",
                    "agent_mode": result.get("agent_mode"),
                    "model_provider": result.get("model_provider"),
                    "model_vendor": result.get("model_vendor"),
                    "model_name": result.get("model_name"),
                    "planner_source": result.get("planner_source"),
                    "intent": result.get("intent"),
                    "planner_confidence": result.get("planner_confidence"),
                    "planner_explanation": result.get("planner_explanation"),
                },
                {"stage": "tool_plan_created", "planned_tools": self._summarize_tools(result.get("tool_plan", []))},
                {"stage": "tool_validated", "tool_plan": self._summarize_tools(result.get("tool_plan", []))},
                {
                    "stage": "risk_scored",
                    "risk_score": result.get("risk_score"),
                    "risk_level": result.get("risk_level"),
                    "risk_factors": result.get("risk_factors", [])[:20],
                },
                {
                    "stage": "security_decision",
                    "security_decision": result.get("security_decision"),
                    "execution_status": result.get("execution_status"),
                    "security_reason": result.get("security_reason"),
                },
                {
                    "stage": "tool_executed",
                    "executed": result.get("executed"),
                    "execution_status": result.get("execution_status"),
                    "environment_message": result.get("environment_message", ""),
                    "executed_tools": [item.get("tool") for item in result.get("tool_results", [])],
                    "blocked_tools": [
                        item.get("tool_name")
                        for item in result.get("tool_plan", [])
                        if item.get("status") == "blocked"
                    ],
                },
                {
                    "stage": "result_summarized",
                    "summary": result.get("summary", "")[:500],
                    "next_step": result.get("next_step", "")[:500],
                    "diagnosis_severity": (result.get("diagnosis") or {}).get("severity"),
                    "evidence": (result.get("diagnosis") or {}).get("evidence", [])[:20],
                },
                {"stage": "audit_saved", "summary": "Audit record prepared for durable storage."},
        ])
        return {
            "request_id": request_id,
            "session_id": session_id,
            "events": events,
        }

    def _summarize_tools(self, tools: list[dict]) -> list[dict]:
        summary = []
        for item in tools[:MAX_CHAT_TOOL_PLAN]:
            summary.append({
                "tool_name": item.get("tool_name"),
                "arguments": item.get("arguments", {}),
                "reason": item.get("reason", ""),
                "status": item.get("status"),
                "risk_score": item.get("risk_score"),
                "error": item.get("error", ""),
            })
        return summary

    def _load_session_context(self, session_id: str, now: float) -> tuple[List[Dict], List[str]]:
        events: List[str] = []
        meta = self._session_meta.get(session_id)
        ttl = max(0, int(config.SESSION_TTL_SECONDS))
        if meta and ttl and now - meta.get("last_seen", now) > ttl:
            self._sessions.pop(session_id, None)
            events = ["session_expired", "session_reset"]
        self._session_meta[session_id] = {"last_seen": now}
        return list(self._sessions.get(session_id, [])), events

    def _trim_context(self, context: List[Dict]) -> List[Dict]:
        session_limit = max(0, int(config.SESSION_MAX_MESSAGES))
        if session_limit == 0:
            return []
        legacy_limit = max(0, int(config.MAX_CONTEXT_ROUNDS) * 2)
        limit = min(session_limit, legacy_limit) if legacy_limit else session_limit
        return context[-limit:]

    def _is_no_action_tool(self, tool_name: Any) -> bool:
        normalized = str(tool_name or "").strip().lower()
        return normalized in {"", "none", "null", "no_tool", "clarify", "unknown"}

    def _log(self, session_id, request_id, user_input, result, start_ms):
        self._prepare_frontend_fields(result)
        duration = int(time.time() * 1000) - start_ms
        tool_result = result.get("tool_result") or {}
        tool_audit = result.get("tool_audit") or {}
        self.audit.log({
            "session_id": session_id,
            "request_id": request_id,
            "user_input": user_input,
            "intent": result.get("intent") or "agent_chat",
            "selected_tool": result.get("selected_tool") or (tool_result.get("tool", "") if isinstance(tool_result, dict) else ""),
            "tool_arguments": result.get("tool_arguments", {}),
            "risk_level": result.get("legacy_risk_level", 1),
            "risk_score": result.get("risk_score"),
            "risk_level_text": result.get("risk_level", ""),
            "legacy_risk_level": result.get("legacy_risk_level", 1),
            "security_decision": result.get("security_decision", ""),
            "security_reason": result.get("security_reason", "executed" if result.get("executed") else ""),
            "matched_rules": result.get("matched_rules", []),
            "risk_factors": result.get("risk_factors", []),
            "confirmation_required": result.get("security_decision") == "confirm",
            "executed": result["executed"],
            "actual_command": tool_audit.get("actual_command", []),
            "executor_user": tool_audit.get("executor_user", ""),
            "execution_success": tool_audit.get("execution_success", False),
            "execution_result": result.get("tool_results") or tool_result,
            "stdout_summary": tool_audit.get("stdout_summary", ""),
            "stderr_summary": tool_audit.get("stderr_summary", ""),
            "final_response": result["response"],
            "rule_hits": result.get("rule_hits", []),
            "session_events": result.get("session_events", []),
            "full_trace_json": self._build_agent_trace(session_id, request_id, user_input, result),
            "duration_ms": duration,
        })

    def _prepare_frontend_fields(self, result: dict) -> None:
        self._apply_diagnosis(result)
        result["rule_labels"] = label_rules(
            result.get("matched_rules", []),
            flatten_rule_hits(result.get("rule_hits", [])),
        )
        if result.get("execution_status") in {"environment_limited", "partial"}:
            if any(item.get("status") == "capability_missing" for item in result.get("tool_plan", [])):
                result["environment_message"] = ENVIRONMENT_LIMITED_MESSAGE
            elif result.get("execution_status") == "environment_limited":
                result["environment_message"] = ENVIRONMENT_LIMITED_MESSAGE
        result.setdefault("environment_message", "")

    def _apply_diagnosis(self, result: dict) -> None:
        diagnosis = build_diagnosis(
            result.get("tool_results", []),
            execution_status=str(result.get("execution_status", "")),
            security_decision=str(result.get("security_decision", "")),
            security_summary=str(result.get("summary") or result.get("response") or ""),
        )
        result["diagnosis"] = diagnosis
        if diagnosis.get("evidence"):
            result["summary"] = diagnosis["summary"]
            result["analysis"] = " ".join(diagnosis.get("findings", []))
            result["next_step"] = " ".join(diagnosis.get("next_actions", []))
            result["response"] = diagnosis["summary"]
