from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiRun, Instrument, JobRun
from app.services.job_events import append_job_event

RESUMABLE_VALUATION_STATUSES = frozenset(
    {"failed", "cancelled", "interrupted", "paused"}
)
TERMINAL_EXECUTION_PHASES = frozenset(
    {
        "awaiting_review",
        "cancelled",
        "completed",
        "failed",
        "interrupted",
        "paused",
        "review_approved",
        "review_rejected",
    }
)


def accumulate_execution_seconds(job: JobRun, ended_at: datetime | None = None) -> float:
    details = dict(job.details or {})
    previous = details.get("execution_seconds")
    total = (
        float(previous)
        if isinstance(previous, (int, float))
        else _legacy_execution_seconds(details)
    )
    if job.started_at is not None:
        end = ended_at or datetime.now(UTC).replace(tzinfo=None)
        total += max((end - job.started_at).total_seconds(), 0)
    details["execution_seconds"] = round(total, 3)
    job.details = details
    return total


def _legacy_execution_seconds(details: dict[str, object]) -> float:
    events = details.get("debug_events")
    if not isinstance(events, list):
        return 0.0
    started_at: datetime | None = None
    total = 0.0
    for event in events:
        if not isinstance(event, dict):
            continue
        phase = event.get("phase")
        timestamp = event.get("at")
        if not isinstance(phase, str) or not isinstance(timestamp, str):
            continue
        at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if at.tzinfo is not None:
            at = at.astimezone(UTC).replace(tzinfo=None)
        if event.get("message") == "任务开始执行":
            started_at = at
        elif started_at is not None and phase in TERMINAL_EXECUTION_PHASES:
            total += max((at - started_at).total_seconds(), 0)
            started_at = None
    return total


def recover_interrupted_jobs(session: Session) -> int:
    """Close jobs left running by a previous worker process."""
    jobs = session.scalars(
        select(JobRun).where(JobRun.status == "running")
    ).all()
    if not jobs:
        return 0

    now = datetime.now(UTC).replace(tzinfo=None)
    for job in jobs:
        previous_phase = job.phase
        accumulate_execution_seconds(job, now)
        session_id = _recover_codex_session_id(session, job)
        message = "服务重启时任务仍在执行，已停止；可恢复后继续"
        job.status = "interrupted"
        job.phase = "interrupted"
        job.error = message
        job.finished_at = now
        job.details = {
            **(job.details or {}),
            "failed_phase": previous_phase,
            "interruption_kind": "service_restart",
            "interrupted_at": now.isoformat(timespec="milliseconds") + "Z",
            **({"codex_session_id": session_id} if session_id else {}),
        }
        append_job_event(job, "interrupted", message)

        ai_runs = session.scalars(
            select(AiRun).where(
                AiRun.job_id == job.id,
                AiRun.status == "running",
            )
        ).all()
        for run in ai_runs:
            run.status = "interrupted"
            run.finished_at = now
            run.stderr = f"{run.stderr}\n{message}".strip()

    session.commit()
    return len(jobs)


def _recover_codex_session_id(session: Session, job: JobRun) -> str | None:
    value = (job.details or {}).get("codex_session_id")
    if isinstance(value, str) and value:
        return value
    latest_run = session.scalar(
        select(AiRun)
        .where(AiRun.job_id == job.id)
        .order_by(AiRun.id.desc())
        .limit(1)
    )
    if latest_run is None:
        return None
    metadata = dict(latest_run.metadata_json or {})
    stored = metadata.get("thread_id")
    if isinstance(stored, str) and stored:
        return stored
    stdout_path = metadata.get("stdout_path")
    if not isinstance(stdout_path, str) or not stdout_path:
        return None
    try:
        with open(stdout_path, encoding="utf-8", errors="replace") as file:
            for line in file:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "thread.started":
                    thread_id = event.get("thread_id")
                    if isinstance(thread_id, str) and thread_id:
                        latest_run.metadata_json = {
                            **metadata,
                            "thread_id": thread_id,
                        }
                        return thread_id
    except OSError:
        return None
    return None


def resume_valuation_job(session: Session, job: JobRun) -> JobRun:
    if job.job_type != "valuation_refresh":
        raise ValueError("只有 Codex 估值任务支持恢复")
    if job.status not in RESUMABLE_VALUATION_STATUSES:
        raise ValueError("当前任务状态不能恢复")

    prefix, _, value = job.scope.partition(":")
    if prefix != "instrument" or not value.isdigit():
        raise ValueError("估值任务缺少有效的标的")
    instrument = session.get(Instrument, int(value))
    if instrument is None:
        raise LookupError("估值标的已不存在")
    if instrument.archived_at is not None:
        raise ValueError("标的已归档，请先恢复标的")

    active = session.scalar(
        select(JobRun)
        .where(
            JobRun.scope == job.scope,
            JobRun.status.in_(("queued", "running", "cancelling")),
            JobRun.id != job.id,
        )
        .limit(1)
    )
    if active is not None:
        raise RuntimeError(f"该标的已有任务 #{active.id} 正在排队或执行")

    details = dict(job.details or {})
    for key in (
        "errors",
        "failed_phase",
        "interrupted_at",
        "paused_from_phase",
        "report_id",
        "review_required",
        "review_status",
    ):
        details.pop(key, None)
    details["resume_count"] = int(details.get("resume_count") or 0) + 1

    job.status = "queued"
    job.phase = "queued"
    job.started_at = None
    job.finished_at = None
    job.error = ""
    job.details = details
    append_job_event(job, "queued", "任务已恢复，等待 worker 重新执行")
    session.commit()
    session.refresh(job)
    return job


def pause_valuation_job(session: Session, job: JobRun) -> JobRun:
    if job.job_type != "valuation_refresh":
        raise ValueError("只有 Codex 估值任务支持暂停")
    if job.status not in {"queued", "running"}:
        raise ValueError("当前任务状态不能暂停")

    previous_phase = job.phase
    now = datetime.now(UTC).replace(tzinfo=None)
    accumulate_execution_seconds(job, now)
    job.status = "paused"
    job.phase = "paused"
    job.finished_at = now
    job.details = {
        **(job.details or {}),
        "paused_from_phase": previous_phase,
    }
    append_job_event(job, "paused", "已请求暂停，Codex 子进程正在停止")
    session.commit()
    session.refresh(job)
    return job
