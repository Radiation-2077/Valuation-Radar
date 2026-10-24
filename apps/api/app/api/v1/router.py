from __future__ import annotations

import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.domain.card_fields import confidence_label
from app.domain.scoring import ALGORITHM_VERSION, DEFAULT_PROFILE, PROFILES
from app.models import AiRun, Instrument, JobRun, ScheduleSetting, ValuationReport
from app.schemas.api import (
    AiRunDebugOut,
    ClearJobsOut,
    CodexMilestoneOut,
    DeleteJobOut,
    InstrumentArchiveOut,
    InstrumentCreate,
    InstrumentCreateOut,
    InstrumentListOut,
    InstrumentPurgeOut,
    JobCreate,
    JobDebugOut,
    JobEventOut,
    JobListOut,
    JobOut,
    MetaResponse,
    ProfileOut,
    RankingResponse,
    ReviewDecisionOut,
    ReviewDeleteOut,
    ReviewListOut,
    ReviewMarketOut,
    ReviewOut,
    ScheduleOut,
    SchedulePatch,
    TokenUsageOut,
    ValuationDetailOut,
)
from app.services.codex_activity import build_codex_activity, extract_codex_usage
from app.services.instruments import (
    InstrumentBusyError,
    InstrumentConflictError,
    InstrumentStateError,
    archive_instrument,
    create_instrument_and_queue,
    purge_instrument,
    restore_instrument,
)
from app.services.job_events import append_job_event
from app.services.job_lifecycle import (
    accumulate_execution_seconds,
    pause_valuation_job,
    resume_valuation_job,
)
from app.services.queries import (
    get_ranking,
    get_valuation_detail,
    list_instruments,
)
from app.services.reviews import (
    approve_review,
    delete_rejected_review,
    list_rejected_reports,
    list_review_reports,
    reject_review,
)
from app.services.schedule import (
    get_or_create_schedule,
    next_run_at,
    queue_job,
)

router = APIRouter(prefix="/api/v1")
SessionDep = Annotated[Session, Depends(get_db)]
ProfileQuery = Annotated[str, Query()]


@router.get("/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    return MetaResponse(
        profiles=[
            ProfileOut(
                code=profile.code,
                label=profile.label,
                description=profile.description,
                weights={
                    "margin": profile.margin,
                    "base": profile.base,
                    "risk": profile.risk,
                    "stability": profile.stability,
                },
            )
            for profile in PROFILES.values()
        ],
        default_profile=DEFAULT_PROFILE,
        algorithm_version=ALGORITHM_VERSION,
    )


@router.get("/dashboard", response_model=RankingResponse)
def dashboard(
    session: SessionDep,
    profile: ProfileQuery = DEFAULT_PROFILE,
    market: str | None = None,
    path: str | None = None,
    industry: str | None = None,
) -> RankingResponse:
    return get_ranking(
        session,
        profile=profile,
        market=market,
        path=path,
        industry=industry,
    )


@router.get("/rankings", response_model=RankingResponse)
def rankings(
    session: SessionDep,
    profile: ProfileQuery = DEFAULT_PROFILE,
    market: str | None = None,
    path: str | None = None,
    industry: str | None = None,
) -> RankingResponse:
    return get_ranking(
        session,
        profile=profile,
        market=market,
        path=path,
        industry=industry,
    )


@router.get("/valuations/{valuation_market_id}", response_model=ValuationDetailOut)
def valuation_detail(
    valuation_market_id: int,
    session: SessionDep,
    profile: ProfileQuery = DEFAULT_PROFILE,
) -> ValuationDetailOut:
    return get_valuation_detail(session, valuation_market_id, profile)


@router.get("/instruments", response_model=InstrumentListOut)
def instruments(session: SessionDep) -> InstrumentListOut:
    return list_instruments(session)


@router.post("/instruments", response_model=InstrumentCreateOut, status_code=202)
def create_instrument(
    payload: InstrumentCreate,
    session: SessionDep,
) -> InstrumentCreateOut:
    try:
        instrument, listing, job = create_instrument_and_queue(
            session,
            name=payload.name,
            code=payload.code,
            asset_type=payload.asset_type,
        )
    except InstrumentConflictError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    session.commit()
    return InstrumentCreateOut(
        instrument_id=instrument.id,
        job_id=job.id,
        name=instrument.name,
        market=listing.market if listing else None,
        code=listing.code if listing else None,
        currency=listing.currency if listing else None,
        asset_type=instrument.asset_type,
        status=job.status,
    )


@router.delete(
    "/instruments/{instrument_id}",
    response_model=InstrumentArchiveOut,
)
def archive(
    instrument_id: int,
    session: SessionDep,
    reason: Annotated[str | None, Query(max_length=200)] = None,
) -> InstrumentArchiveOut:
    try:
        instrument = archive_instrument(session, instrument_id, reason=reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    except InstrumentBusyError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    session.commit()
    return InstrumentArchiveOut(
        instrument_id=instrument.id,
        name=instrument.name,
        status="archived",
        archived_at=instrument.archived_at,
        archive_reason=instrument.archive_reason,
    )


@router.post(
    "/instruments/{instrument_id}/restore",
    response_model=InstrumentArchiveOut,
)
def restore(instrument_id: int, session: SessionDep) -> InstrumentArchiveOut:
    try:
        instrument = restore_instrument(session, instrument_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    session.commit()
    return InstrumentArchiveOut(
        instrument_id=instrument.id,
        name=instrument.name,
        status="active",
        archived_at=instrument.archived_at,
        archive_reason=instrument.archive_reason,
    )


@router.delete(
    "/instruments/{instrument_id}/purge",
    response_model=InstrumentPurgeOut,
)
def purge(
    instrument_id: int,
    session: SessionDep,
    confirmation: Annotated[str, Query(min_length=1, max_length=100)],
) -> InstrumentPurgeOut:
    try:
        result = purge_instrument(
            session,
            instrument_id,
            confirmation=confirmation,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    except (InstrumentBusyError, InstrumentStateError) as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    session.commit()
    _remove_staging_for_jobs(result.job_ids)
    return InstrumentPurgeOut(
        instrument_id=result.instrument_id,
        name=result.name,
        deleted_listings=result.deleted_listings,
        deleted_reports=result.deleted_reports,
        deleted_jobs=result.deleted_jobs,
    )


@router.get("/schedule", response_model=ScheduleOut)
def get_schedule(session: SessionDep) -> ScheduleOut:
    schedule = get_or_create_schedule(session)
    session.commit()
    return _schedule_out(schedule)


@router.patch("/schedule", response_model=ScheduleOut)
def update_schedule(payload: SchedulePatch, session: SessionDep) -> ScheduleOut:
    schedule = get_or_create_schedule(session)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, key, value)
    session.commit()
    session.refresh(schedule)
    return _schedule_out(schedule)


@router.get("/jobs", response_model=JobListOut)
def list_jobs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JobListOut:
    jobs = session.scalars(
        select(JobRun).order_by(JobRun.id.desc()).limit(limit)
    ).all()
    return JobListOut(items=[_job_out(job, session) for job in jobs])


@router.delete("/jobs", response_model=ClearJobsOut)
def clear_jobs(session: SessionDep) -> ClearJobsOut:
    active = session.scalar(
        select(func.count())
        .select_from(JobRun)
        .where(JobRun.status.in_(("queued", "running", "cancelling")))
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail={"message": "存在排队中或执行中的任务，暂时不能清除任务记录"},
        )
    deleted = session.scalar(select(func.count()).select_from(JobRun)) or 0
    session.execute(delete(JobRun))
    session.commit()
    return ClearJobsOut(deleted=deleted)


@router.delete("/jobs/{job_id}", response_model=DeleteJobOut)
def delete_job(job_id: int, session: SessionDep) -> DeleteJobOut:
    job = session.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    terminated = job.status in {"queued", "running", "cancelling"}
    was_running = job.status in {"running", "cancelling"}
    if job.status in {"queued", "running"}:
        job.status = "cancelling"
        append_job_event(job, "cancelling", "收到删除请求，正在终止任务")
        session.commit()

    if terminated and was_running:
        for _ in range(80):
            with Session(bind=session.get_bind()) as monitor:
                live = monitor.get(JobRun, job_id)
                if live is None or live.status not in {"running", "cancelling"}:
                    break
            time.sleep(0.25)
        else:
            raise HTTPException(
                status_code=409,
                detail={"message": "任务暂停请求已发出，但进程尚未退出，请稍后重试删除"},
            )

    session.expire_all()
    job = session.get(JobRun, job_id)
    if job is None:
        return DeleteJobOut(job_id=job_id, deleted=True, terminated=terminated)
    session.execute(delete(AiRun).where(AiRun.job_id == job_id))
    session.delete(job)
    session.commit()
    _remove_staging_for_jobs((job_id,))
    return DeleteJobOut(job_id=job_id, deleted=True, terminated=terminated)


@router.post("/jobs", response_model=JobOut, status_code=202)
def create_job(
    payload: JobCreate,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobOut:
    job, _ = queue_job(
        session,
        job_type=payload.job_type,
        trigger="manual",
        scope=payload.scope,
        scheduled_for=datetime.now(UTC).replace(tzinfo=None),
        idempotency_key=idempotency_key,
    )
    session.commit()
    session.refresh(job)
    return _job_out(job, session)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, session: SessionDep) -> JobOut:
    job = session.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    return _job_out(job, session)


@router.get("/jobs/{job_id}/debug", response_model=JobDebugOut)
def get_job_debug(job_id: int, session: SessionDep) -> JobDebugOut:
    job = session.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    ai_runs = session.scalars(
        select(AiRun).where(AiRun.job_id == job_id).order_by(AiRun.id)
    ).all()
    raw_events = (job.details or {}).get("debug_events")
    event_items = raw_events if isinstance(raw_events, list) else []
    events = [
        JobEventOut(
            at=str(event.get("at") or ""),
            phase=str(event.get("phase") or ""),
            message=str(event.get("message") or ""),
        )
        for event in event_items
        if isinstance(event, dict)
    ]
    latest = ai_runs[-1] if ai_runs else None
    metadata = dict(latest.metadata_json or {}) if latest else {}
    storage_root = get_settings().storage_root
    stdout = _read_log_tail(metadata.get("stdout_path"), storage_root)
    current_action, codex_event_data = build_codex_activity(
        stdout,
        running=job.status in {"queued", "running"},
    )
    if latest is None:
        current_action = _job_current_action(job)
    return JobDebugOut(
        job=_job_out(job, session),
        events=events,
        ai_runs=[_ai_run_debug_out(run, storage_root) for run in ai_runs],
        current_action=current_action,
        codex_events=[
            CodexMilestoneOut(**event) for event in codex_event_data
        ],
    )


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int, session: SessionDep) -> JobOut:
    job = session.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    if job.status in {"queued", "running"}:
        finished_at = datetime.now(UTC).replace(tzinfo=None)
        if job.status == "running":
            accumulate_execution_seconds(job, finished_at)
        job.status = "cancelled"
        job.phase = "cancelled"
        job.finished_at = finished_at
        session.commit()
        session.refresh(job)
    return _job_out(job, session)


@router.post(
    "/jobs/{job_id}/resume",
    response_model=JobOut,
    status_code=202,
)
def resume_job(job_id: int, session: SessionDep) -> JobOut:
    job = session.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    try:
        job = resume_valuation_job(session, job)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return _job_out(job, session)


@router.post("/jobs/{job_id}/pause", response_model=JobOut)
def pause_job(job_id: int, session: SessionDep) -> JobOut:
    job = session.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    try:
        job = pause_valuation_job(session, job)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return _job_out(job, session)


@router.post(
    "/instruments/{instrument_id}/revaluations",
    response_model=JobOut,
    status_code=202,
)
def request_revaluation(
    instrument_id: int,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobOut:
    instrument = session.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status_code=404, detail={"message": "标的不存在"})
    if instrument.archived_at is not None:
        raise HTTPException(
            status_code=409,
            detail={"message": "标的已归档，请先恢复后再重新估值"},
        )
    job, _ = queue_job(
        session,
        job_type="valuation_refresh",
        trigger="manual",
        scope=f"instrument:{instrument_id}",
        scheduled_for=datetime.now(UTC).replace(tzinfo=None),
        idempotency_key=idempotency_key,
    )
    job.details = {**(job.details or {}), "instrument": instrument.name}
    session.commit()
    session.refresh(job)
    return _job_out(job, session)


@router.get("/reviews", response_model=ReviewListOut)
def reviews(session: SessionDep) -> ReviewListOut:
    return ReviewListOut(items=[_review_out(report) for report in list_review_reports(session)])


@router.get("/reviews/rejected", response_model=ReviewListOut)
def rejected_reviews(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReviewListOut:
    return ReviewListOut(
        items=[
            _review_out(report)
            for report in list_rejected_reports(session, limit=limit)
        ]
    )


@router.post("/reviews/{report_id}/approve", response_model=ReviewDecisionOut)
def approve(report_id: int, session: SessionDep) -> ReviewDecisionOut:
    try:
        report = approve_review(session, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return ReviewDecisionOut(report_id=report.id, status=report.status, ranking_rebuilt=True)


@router.post("/reviews/{report_id}/reject", response_model=ReviewDecisionOut)
def reject(report_id: int, session: SessionDep) -> ReviewDecisionOut:
    try:
        report = reject_review(session, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return ReviewDecisionOut(report_id=report.id, status=report.status, ranking_rebuilt=False)


@router.delete("/reviews/{report_id}", response_model=ReviewDeleteOut)
def delete_rejected(report_id: int, session: SessionDep) -> ReviewDeleteOut:
    try:
        delete_rejected_review(session, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return ReviewDeleteOut(report_id=report_id, deleted=True)


def _schedule_out(schedule: ScheduleSetting) -> ScheduleOut:
    return ScheduleOut(
        enabled=schedule.enabled,
        frequency=schedule.frequency,
        run_time=schedule.run_time,
        timezone=schedule.timezone,
        calendar_mode=schedule.calendar_mode,
        scope=schedule.scope,
        revaluation_mode=schedule.revaluation_mode,
        publish_mode=schedule.publish_mode,
        stale_after_days=schedule.stale_after_days,
        next_run_at=next_run_at(schedule),
        updated_at=schedule.updated_at,
    )


def _job_out(job: JobRun, session: Session | None = None) -> JobOut:
    phase = job.phase
    details = dict(job.details or {})
    if session is not None and job.job_type == "valuation_refresh":
        report_id = details.get("report_id")
        if isinstance(report_id, int):
            report = session.get(ValuationReport, report_id)
            if report is not None:
                details["review_status"] = report.status
                if job.phase == "awaiting_review":
                    phase = {
                        "published": "review_approved",
                        "rejected": "review_rejected",
                    }.get(report.status, job.phase)
    return JobOut(
        id=job.id,
        job_type=job.job_type,
        trigger=job.trigger,
        scope=job.scope,
        status=job.status,
        phase=phase,
        scheduled_for=job.scheduled_for,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        details=details,
        created_at=job.created_at,
    )


def _ai_run_debug_out(run: AiRun, storage_root: Path) -> AiRunDebugOut:
    metadata = dict(run.metadata_json or {})
    usage = extract_codex_usage(
        _read_log_tail(metadata.get("stdout_path"), storage_root)
    )
    return AiRunDebugOut(
        id=run.id,
        status=run.status,
        model=run.model,
        cli_version=run.cli_version,
        exit_code=run.exit_code,
        prompt_path=run.prompt_path,
        output_path=run.output_path,
        stderr=run.stderr,
        metadata=metadata,
        started_at=run.started_at,
        finished_at=run.finished_at,
        token_usage=TokenUsageOut(**usage) if usage else None,
    )


def _read_log_tail(value: object, storage_root: Path) -> str:
    if not isinstance(value, str) or not value:
        return ""
    path = Path(value).resolve()
    root = storage_root.resolve()
    if path != root and root not in path.parents:
        return ""
    if not path.is_file():
        return ""
    with path.open("rb") as file:
        file.seek(0, 2)
        size = file.tell()
        file.seek(max(0, size - 2_000_000))
        return file.read().decode("utf-8", errors="replace")


def _job_current_action(job: JobRun) -> str:
    actions = {
        "queued": "任务正在排队",
        "fetching": "正在抓取最新行情",
        "saving_quotes": "正在写入行情快照",
        "loading_macro": "正在更新宏观缓存",
        "rebuilding_ranking": "正在重算排名",
        "finalizing": "正在整理任务结果",
        "awaiting_review": "等待人工复核",
        "interrupted": "任务因服务重启中断，可恢复执行",
        "paused": "任务已暂停，可恢复执行",
        "review_approved": "候选估值已批准并发布",
        "review_rejected": "候选估值已拒绝",
        "completed": "任务已完成",
        "failed": "任务失败",
        "cancelled": "任务已取消",
    }
    return actions.get(job.phase, f"当前阶段：{job.phase}")


def _review_out(report: ValuationReport) -> ReviewOut:
    conclusion = report.raw_card.get("conclusion") or {}
    return ReviewOut(
        report_id=report.id,
        instrument_id=report.instrument_id,
        name=report.instrument.name,
        analysis_date=report.analysis_date,
        generated_at=report.generated_at,
        thesis=str(conclusion.get("thesis") or ""),
        confidence=confidence_label(conclusion.get("confidence"), ""),
        markets=[
            ReviewMarketOut(
                valuation_market_id=market.id,
                market=market.listing.market,
                code=market.listing.code,
                currency=market.listing.currency,
                price=market.price,
                fair_mid=market.fair_mid,
                verdict=market.verdict,
            )
            for market in report.markets
        ],
    )


def _remove_staging_for_jobs(job_ids: tuple[int, ...]) -> None:
    root = get_settings().staging_dir.resolve()
    for job_id in job_ids:
        target = (root / f"job-{job_id}").resolve()
        if target.parent != root or not target.is_dir():
            continue
        try:
            shutil.rmtree(target)
        except OSError:
            continue
