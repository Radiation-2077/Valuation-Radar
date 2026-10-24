from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AiRun,
    Instrument,
    JobRun,
    RankingEntry,
    ValuationMarket,
    ValuationReport,
)
from app.services.importer import apply_instrument_metadata
from app.services.job_events import append_job_event
from app.services.ranking import RankingService


def list_review_reports(session: Session) -> list[ValuationReport]:
    return list(
        session.scalars(
            select(ValuationReport)
            .join(Instrument, Instrument.id == ValuationReport.instrument_id)
            .where(ValuationReport.status == "needs_review")
            .where(Instrument.archived_at.is_(None))
            .options(
                selectinload(ValuationReport.instrument),
                selectinload(ValuationReport.markets).selectinload(ValuationMarket.listing),
            )
            .order_by(ValuationReport.generated_at.desc(), ValuationReport.id.desc())
        )
        .unique()
        .all()
    )


def list_rejected_reports(
    session: Session,
    *,
    limit: int = 20,
) -> list[ValuationReport]:
    return list(
        session.scalars(
            select(ValuationReport)
            .join(Instrument, Instrument.id == ValuationReport.instrument_id)
            .where(
                ValuationReport.status == "rejected",
                Instrument.archived_at.is_(None),
            )
            .options(
                selectinload(ValuationReport.instrument),
                selectinload(ValuationReport.markets).selectinload(ValuationMarket.listing),
            )
            .order_by(ValuationReport.generated_at.desc(), ValuationReport.id.desc())
            .limit(limit)
        )
        .unique()
        .all()
    )


def approve_review(session: Session, report_id: int) -> ValuationReport:
    report = session.get(ValuationReport, report_id)
    if report is None:
        raise ValueError("候选估值不存在")
    if report.instrument.archived_at is not None:
        raise ValueError("标的已归档，不能批准候选估值")
    if report.status != "needs_review":
        raise ValueError(f"候选估值当前状态为 {report.status}")
    report.status = "published"
    report.generated_at = report.generated_at or datetime.now(UTC).replace(tzinfo=None)
    apply_instrument_metadata(report.instrument, report.raw_card)
    _sync_review_jobs(
        session,
        report,
        phase="review_approved",
        message="候选估值已批准并发布",
    )
    session.flush()
    RankingService().rebuild(session)
    session.commit()
    return report


def reject_review(session: Session, report_id: int) -> ValuationReport:
    report = session.get(ValuationReport, report_id)
    if report is None:
        raise ValueError("候选估值不存在")
    if report.status != "needs_review":
        raise ValueError(f"候选估值当前状态为 {report.status}")
    report.status = "rejected"
    _sync_review_jobs(
        session,
        report,
        phase="review_rejected",
        message="候选估值已拒绝",
    )
    session.commit()
    return report


def delete_rejected_review(session: Session, report_id: int) -> ValuationReport:
    report = session.get(ValuationReport, report_id)
    if report is None:
        raise ValueError("候选估值不存在")
    if report.status != "rejected":
        raise ValueError("只能删除已拒绝的候选估值")
    market_ids = [market.id for market in report.markets]
    if market_ids:
        session.execute(
            delete(RankingEntry).where(
                RankingEntry.valuation_market_id.in_(market_ids)
            )
        )
    session.delete(report)
    session.commit()
    return report


def _sync_review_jobs(
    session: Session,
    report: ValuationReport,
    *,
    phase: str,
    message: str,
) -> None:
    ai_runs = session.scalars(
        select(AiRun).where(AiRun.instrument_id == report.instrument_id)
    ).all()
    report_job_ids = {
        run.job_id
        for run in ai_runs
        if (run.metadata_json or {}).get("report_id") == report.id
    }
    jobs = session.scalars(
        select(JobRun)
        .where(
            JobRun.job_type == "valuation_refresh",
            JobRun.scope == f"instrument:{report.instrument_id}",
        )
        .order_by(JobRun.id)
    ).all()
    for job in jobs:
        details = dict(job.details or {})
        if job.id not in report_job_ids and details.get("report_id") != report.id:
            continue
        job.details = {
            **details,
            "report_id": report.id,
            "review_required": False,
            "review_status": report.status,
        }
        append_job_event(job, phase, message)
