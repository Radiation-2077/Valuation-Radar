from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Instrument, ValuationMarket, ValuationReport
from app.services.importer import apply_instrument_metadata
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
    session.commit()
    return report
