from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import JobRun
from app.services.job_events import append_job_event
from app.services.job_lifecycle import (
    accumulate_execution_seconds,
    recover_interrupted_jobs,
)
from app.services.refresh import RefreshSummary, refresh_market_data
from app.services.revaluation import (
    ValuationPaused,
    ValuationStopped,
    run_valuation_refresh,
)
from app.services.schedule import scheduler_tick


def process_next_job() -> bool:
    with SessionLocal() as session:
        job = session.scalar(
            select(JobRun)
            .where(JobRun.status == "queued")
            .order_by(JobRun.id)
            .limit(1)
        )
        if job is None:
            return False
        job_id = job.id
        current_phase = "valuing" if job.job_type == "valuation_refresh" else "fetching"
        details: dict[str, Any] = {}
        job.status = "running"
        append_job_event(job, current_phase, "任务开始执行")
        job.started_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()

        def update_phase(phase: str) -> None:
            nonlocal current_phase
            current_phase = phase
            live = session.get(JobRun, job_id)
            if live is None or live.status in {"cancelled", "paused"}:
                return
            if live.phase != phase:
                append_job_event(live, phase, _phase_message(phase))
            live.details = {**live.details, **details}
            session.commit()

        try:
            if job.job_type == "market_refresh":
                summary = refresh_market_data(
                    session,
                    get_settings(),
                    on_phase=update_phase,
                )
                details = _market_refresh_details(summary)
                if summary.quotes_fetched == 0:
                    current_phase = "fetching"
                    diagnostic = "；".join(summary.quote_errors) or "行情源未返回有效报价"
                    raise RuntimeError(f"本轮没有取得任何有效行情：{diagnostic}")
                update_phase("finalizing")
                job.status = "partial" if summary.quote_errors else "succeeded"
                job.details = {**job.details, **details}
                append_job_event(job, "completed", "任务完成")
            elif job.job_type == "valuation_refresh":
                report = run_valuation_refresh(session, job, get_settings())
                job.status = "succeeded"
                details = {
                    "report_id": report.id,
                    "instrument": report.instrument.name,
                    "review_required": True,
                }
                append_job_event(job, "awaiting_review", "候选估值已生成，等待人工复核")
                job.details = {**job.details, **details}
            else:
                raise ValueError(f"暂不支持任务类型：{job.job_type}")
            job.finished_at = datetime.now(UTC).replace(tzinfo=None)
            accumulate_execution_seconds(job, job.finished_at)
            session.commit()
            print(json.dumps({"job_id": job_id, **details}, ensure_ascii=False), flush=True)
        except ValuationPaused as exc:
            session.rollback()
            paused = session.get(JobRun, job_id)
            if paused is not None:
                paused.finished_at = datetime.now(UTC).replace(tzinfo=None)
                session.commit()
            print(f"job {job_id} paused: {exc}", flush=True)
        except ValuationStopped as exc:
            session.rollback()
            stopped = session.get(JobRun, job_id)
            if stopped is not None:
                stopped.status = "cancelled"
                stopped.phase = "cancelled"
                stopped.finished_at = datetime.now(UTC).replace(tzinfo=None)
                session.commit()
            print(f"job {job_id} stopped: {exc}", flush=True)
        except Exception as exc:
            session.rollback()
            failed = session.get(JobRun, job_id)
            if failed is not None and failed.status not in {"cancelled", "cancelling"}:
                failed.status = "failed"
                failed.phase = current_phase
                failed.error = str(exc)
                errors = details.get("errors")
                detail_errors = list(errors) if isinstance(errors, list) else []
                if str(exc) not in detail_errors:
                    detail_errors.append(str(exc))
                failed.details = {
                    **failed.details,
                    **details,
                    "failed_phase": current_phase,
                    "errors": detail_errors,
                }
                append_job_event(failed, current_phase, f"任务失败：{exc}")
                failed.finished_at = datetime.now(UTC).replace(tzinfo=None)
                accumulate_execution_seconds(failed, failed.finished_at)
                session.commit()
            print(f"job {job_id} failed: {exc}", flush=True)
        return True


def _market_refresh_details(summary: RefreshSummary) -> dict[str, Any]:
    return {
        "listings": summary.listings,
        "quotes_fetched": summary.quotes_fetched,
        "quotes_saved": summary.quotes_saved,
        "quotes_unchanged": summary.quotes_unchanged,
        "macro_observations": summary.macro_observations,
        "ranking_runs": summary.ranking_runs,
        "ranking_reused": summary.ranking_reused,
        "latest_quote_at": (
            summary.latest_quote_at.isoformat() if summary.latest_quote_at else None
        ),
        "errors": summary.quote_errors,
    }


def _phase_message(phase: str) -> str:
    messages = {
        "fetching": "开始抓取最新行情",
        "saving_quotes": "写入行情快照并执行时间戳去重",
        "loading_macro": "更新宏观缓存",
        "rebuilding_ranking": "行情或宏观发生变化，重算排名",
        "finalizing": "整理任务结果",
    }
    return messages.get(phase, phase)


def run_worker(poll_seconds: float = 3.0) -> None:
    print("valuation worker started", flush=True)
    with SessionLocal() as session:
        recovered = recover_interrupted_jobs(session)
    if recovered:
        print(f"marked {recovered} interrupted jobs for recovery", flush=True)
    while True:
        if not process_next_job():
            time.sleep(poll_seconds)


def run_scheduler(poll_seconds: float = 20.0) -> None:
    print("valuation scheduler started", flush=True)
    while True:
        with SessionLocal() as session:
            job = scheduler_tick(session)
            if job is not None:
                session.commit()
                print(f"queued scheduled refresh: {job.id}", flush=True)
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(prog="valuation-worker")
    parser.add_argument("role", choices=("worker", "scheduler"))
    args = parser.parse_args()
    if args.role == "worker":
        run_worker()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
