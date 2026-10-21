from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import JobRun
from app.services.refresh import refresh_market_data
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
        job.status = "running"
        job.phase = "fetching"
        job.started_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()

        try:
            if job.job_type != "market_refresh":
                raise ValueError(f"暂不支持任务类型：{job.job_type}")
            summary = refresh_market_data(session, get_settings())
            if summary.quotes_saved == 0:
                raise RuntimeError("本轮没有取得任何有效行情")
            job.phase = "completed"
            job.status = "partial" if summary.quote_errors else "succeeded"
            job.finished_at = datetime.now(UTC).replace(tzinfo=None)
            job.details = {
                "listings": summary.listings,
                "quotes_saved": summary.quotes_saved,
                "macro_observations": summary.macro_observations,
                "ranking_runs": summary.ranking_runs,
                "errors": summary.quote_errors,
            }
            session.commit()
            print(json.dumps({"job_id": job.id, **job.details}, ensure_ascii=False), flush=True)
        except Exception as exc:
            session.rollback()
            failed = session.get(JobRun, job.id)
            if failed is not None:
                failed.status = "failed"
                failed.phase = "failed"
                failed.error = str(exc)
                failed.finished_at = datetime.now(UTC).replace(tzinfo=None)
                session.commit()
            print(f"job {job.id} failed: {exc}", flush=True)
        return True


def run_worker(poll_seconds: float = 3.0) -> None:
    print("valuation worker started", flush=True)
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
