"""Tool: zombie_process_check - detect zombie processes and identify parents.

Competition scenario explicitly names "zombie process accumulation". This
tool is read-only: it lists processes in Z state, identifies their parent
processes, and produces safe handling advice. Zombies cannot be killed
directly (they are already dead); the parent must reap them, or the
parent service must be restarted.
"""
from __future__ import annotations

from typing import Any

from backend.executor import SafeExecutor

from .registry import ToolResult, ToolSchema, command_audit, get_registry

_executor = SafeExecutor()


def _zombie_process_check() -> ToolResult:
    cmd = ["ps", "-eo", "pid,ppid,user,stat,comm,args"]
    result = _executor.run(cmd)
    if not result.success:
        err = result.error or result.stderr or "ps not available"
        status = "capability_missing" if "not found" in err.lower() else "command_failed"
        return ToolResult(
            tool="zombie_process_check",
            status=status,
            error=err,
            audit=command_audit(result) if hasattr(result, "command") else {},
        )

    lines = result.stdout.strip().split("\n")
    if len(lines) <= 1:
        return ToolResult(
            tool="zombie_process_check",
            status="success",
            data={"zombie_count": 0, "zombies": [], "parents": [], "recommendation": "未发现僵尸进程。"},
            raw_output="no processes",
            audit=command_audit(result),
        )

    zombies: list[dict[str, Any]] = []
    parent_pids: set[str] = set()
    for line in lines[1:]:
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        pid, ppid, user, stat, comm = parts[0], parts[1], parts[2], parts[3], parts[4]
        args = parts[5] if len(parts) > 5 else comm
        if "Z" in stat or "z" in stat:
            zombies.append({
                "pid": pid,
                "ppid": ppid,
                "user": user,
                "stat": stat,
                "comm": comm,
                "args": args,
            })
            parent_pids.add(ppid)

    parents = _get_parent_info(parent_pids) if parent_pids else []
    recommendation = _build_recommendation(zombies, parents)

    return ToolResult(
        tool="zombie_process_check",
        status="success",
        data={
            "zombie_count": len(zombies),
            "zombies": zombies,
            "parents": parents,
            "recommendation": recommendation,
        },
        raw_output=f"found {len(zombies)} zombie processes, {len(parents)} parents",
        audit=command_audit(result),
    )


def _get_parent_info(ppids: set[str]) -> list[dict[str, Any]]:
    """Look up parent process details for each zombie's PPID."""
    pid_list = ",".join(sorted(ppids))
    if not pid_list:
        return []
    cmd = ["ps", "-o", "pid,user,stat,comm,args", "-p", pid_list]
    result = _executor.run(cmd)
    if not result.success:
        return [{"ppid": pid, "note": "父进程信息查询失败"} for pid in sorted(ppids)]

    lines = result.stdout.strip().split("\n")
    parents: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        pid, user, stat, comm = parts[0], parts[1], parts[2], parts[3]
        args = parts[4] if len(parts) > 4 else comm
        parents.append({
            "ppid": pid,
            "user": user,
            "stat": stat,
            "comm": comm,
            "args": args,
            "is_init": pid == "1",
        })
    return parents


def _build_recommendation(zombies: list[dict[str, Any]], parents: list[dict[str, Any]]) -> str:
    if not zombies:
        return "未发现僵尸进程，当前系统进程状态正常。"

    parts = [f"检测到 {len(zombies)} 个僵尸进程。"]
    init_parents = [p for p in parents if p.get("is_init")]
    service_parents = [p for p in parents if not p.get("is_init")]

    if init_parents and not service_parents:
        parts.append("僵尸进程的父进程为 init(PID 1)，通常会被 init 自动 reap，可能是临时状态，建议间隔复测。")
    elif service_parents:
        names = sorted({p.get("comm", "未知") for p in service_parents})
        parts.append(f"僵尸进程由 {', '.join(names)} 等服务产生，这些服务未正确回收子进程。")
        parts.append("安全处置建议：不能直接 kill 僵尸进程（已死亡），需重启产生僵尸的父服务让其重新 reap，或由管理员检查父服务代码的子进程回收逻辑。")
    else:
        parts.append("建议由管理员核对父进程并决定是否重启父服务。")

    return " ".join(parts)


SCHEMA = ToolSchema(
    name="zombie_process_check",
    description="Detect zombie (Z state) processes, identify their parent processes, and produce safe handling advice",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def register() -> None:
    get_registry().register(SCHEMA, lambda: _zombie_process_check())
