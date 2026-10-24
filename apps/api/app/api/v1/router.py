from __future__ import annotations

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
    InstrumentCreate,
    InstrumentCreateOut,
    InstrumentListOut,
    JobCreate,
    JobDebugOut,
    JobEventOut,
    JobListOut,
    JobOut,
    MetaResponse,
    ProfileOut,
    RankingResponse,
    ReviewDecisionOut,
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
    InstrumentConflictError,
    create_instrument_and_queue,
)
from app.services.queries import (
    get_ranking,
    get_valuation_detail,
    list_instruments,
)
from app.services.reviews import (
    approve_review,
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
    return JobListOut(items=[_job_out(job) for job in jobs])


@router.delete("/jobs", response_model=ClearJobsOut)
def clear_jobs(session: SessionDep) -> ClearJobsOut:
    active = session.scalar(
        select(func.count())
        .select_from(JobRun)
        .where(JobRun.status.in_(("queued", "running")))
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
    return _job_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, session: SessionDep) -> JobOut:
    job = session.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    return _job_out(job)


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
        job=_job_out(job),
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
        job.status = "cancelled"
        job.phase = "cancelled"
        job.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
        session.refresh(job)
    return _job_out(job)


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
    return _job_out(job)


@router.get("/reviews", response_model=ReviewListOut)
def reviews(session: SessionDep) -> ReviewListOut:
    return ReviewListOut(items=[_review_out(report) for report in list_review_reports(session)])


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


def _job_out(job: JobRun) -> JobOut:
    return JobOut(
        id=job.id,
        job_type=job.job_type,
        trigger=job.trigger,
        scope=job.scope,
        status=job.status,
        phase=job.phase,
        scheduled_for=job.scheduled_for,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        details=job.details,
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
