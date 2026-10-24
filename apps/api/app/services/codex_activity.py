from __future__ import annotations

import json
from typing import Any

MAX_MILESTONES = 30
TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def extract_codex_usage(raw: str) -> dict[str, int] | None:
    for line in reversed(raw.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        usage = event.get("usage")
        if not isinstance(usage, dict):
            return None
        parsed = {
            key: int(usage[key])
            for key in TOKEN_FIELDS
            if isinstance(usage.get(key), int)
        }
        return parsed if parsed else None
    return None


def build_codex_activity(
    raw: str,
    *,
    running: bool,
) -> tuple[str, list[dict[str, Any]]]:
    milestones: list[dict[str, Any]] = []
    current_action = (
        "Codex 已启动，正在准备任务"
        if running
        else "Codex 执行已结束"
    )

    def append(kind: str, message: str) -> None:
        if not message:
            return
        if milestones and milestones[-1]["message"] == message:
            return
        milestones.append(
            {
                "sequence": len(milestones) + 1,
                "kind": kind,
                "message": message,
            }
        )

    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        item = event.get("item")
        item = item if isinstance(item, dict) else {}
        item_type = str(item.get("type") or "")

        if event_type == "thread.started":
            append("info", "Codex 会话已建立")
        elif event_type == "turn.started":
            current_action = "Codex 正在读取任务与数据"
            append("info", "Codex 开始执行估值任务")
        elif event_type == "item.started" and item_type == "command_execution":
            goal = _command_goal(str(item.get("command") or ""))
            if goal:
                current_action = f"正在{goal}"
        elif event_type == "item.completed" and item_type == "command_execution":
            if current_action.startswith("正在"):
                current_action = "正在整理上一步检索与计算结果"
        elif event_type == "item.completed" and item_type == "file_change":
            if not any(
                item["message"] == "已写入或更新候选数据卡"
                for item in milestones
            ):
                append("success", "已写入或更新候选数据卡")
            current_action = "正在复核候选数据卡"
        elif event_type == "item.completed" and item_type == "agent_message":
            message = _agent_milestone(str(item.get("text") or item.get("message") or ""))
            if message:
                append("milestone", message)
                current_action = "已完成一步分析，继续核验"
        elif event_type == "turn.completed":
            current_action = "Codex 执行完成"
            append("success", "Codex 回合完成，等待候选校验")
        elif event_type in {"turn.failed", "error"} or event.get("error"):
            current_action = "Codex 执行失败"
            append("error", _shorten(str(event.get("error") or "Codex 执行失败"), 180))

    return current_action, milestones[-MAX_MILESTONES:]


def _command_goal(command: str) -> str | None:
    lowered = command.lower()
    if "scorecard.py validate" in lowered:
        return "校验候选数据卡"
    if "cache.py put" in lowered or "cache.py refresh" in lowered:
        return "更新通用宏观与汇率缓存"
    if any(name in lowered for name in ("curl ", "wget ", "requests.", "httpx.")):
        return "检索并交叉核验外部数据"
    if "pdftotext" in lowered or ".pdf" in lowered:
        return "提取财报与公告指标"
    if "python3" in lowered:
        return "复算估值与市场数据"
    if "file_change" in lowered:
        return "生成候选数据卡"
    if any(name in lowered for name in ("find data", "ls data", "rg ", "grep ")):
        return "核对任务产物与约束"
    return None


def _agent_milestone(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            manifest = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(manifest, dict) and manifest.get("status") == "ok":
                return "候选数据卡与交付说明已生成"
    return _shorten(stripped, 220)


def _shorten(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}…"
