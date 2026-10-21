from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as exchange_calendars
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobRun, ScheduleSetting

VALID_FREQUENCIES = {"trading_daily", "weekly", "manual"}
VALID_CALENDARS = {"CN", "HK", "ANY"}


def get_or_create_schedule(session: Session) -> ScheduleSetting:
    schedule = session.scalar(select(ScheduleSetting).order_by(ScheduleSetting.id).limit(1))
    if schedule is None:
        schedule = ScheduleSetting()
        session.add(schedule)
        session.flush()
    return schedule


def is_due(
    schedule: ScheduleSetting,
    now: datetime | None = None,
) -> bool:
    if not schedule.enabled or schedule.frequency == "manual":
        return False
    local_now = _local_now(schedule, now)
    if not _frequency_matches(schedule, local_now.date()):
        return False
    if not _market_is_open(local_now.date(), schedule.calendar_mode):
        return False
    return local_now.time() >= _schedule_time(schedule)


def next_run_at(
    schedule: ScheduleSetting,
    now: datetime | None = None,
) -> datetime | None:
    if not schedule.enabled or schedule.frequency == "manual":
        return None
    local_now = _local_now(schedule, now)
    for offset in range(15):
        candidate_date = local_now.date() + timedelta(days=offset)
        if not _frequency_matches(schedule, candidate_date):
            continue
        if not _market_is_open(candidate_date, schedule.calendar_mode):
            continue
        candidate = datetime.combine(
            candidate_date,
            _schedule_time(schedule),
            tzinfo=ZoneInfo(schedule.timezone),
        )
        if candidate > local_now:
            return candidate
    return None


def queue_job(
    session: Session,
    job_type: str,
    trigger: str,
    scope: str,
    scheduled_for: datetime | None = None,
    idempotency_key: str | None = None,
) -> tuple[JobRun, bool]:
    key = idempotency_key or f"{job_type}:{trigger}:{uuid.uuid4()}"
    existing = session.scalar(select(JobRun).where(JobRun.idempotency_key == key))
    if existing is not None:
        return existing, False
    job = JobRun(
        job_type=job_type,
        trigger=trigger,
        scope=scope,
        idempotency_key=key,
        scheduled_for=scheduled_for,
        status="queued",
        phase="queued",
    )
    session.add(job)
    session.flush()
    return job, True


def scheduler_tick(
    session: Session,
    now: datetime | None = None,
) -> JobRun | None:
    schedule = get_or_create_schedule(session)
    if not is_due(schedule, now):
        return None
    local_now = _local_now(schedule, now)
    job, created = queue_job(
        session,
        job_type="market_refresh",
        trigger="schedule",
        scope=schedule.scope,
        scheduled_for=local_now.astimezone(UTC).replace(tzinfo=None),
        idempotency_key=f"market-refresh:{local_now.date().isoformat()}:{schedule.scope}",
    )
    return job if created else None


def _local_now(schedule: ScheduleSetting, now: datetime | None) -> datetime:
    zone = ZoneInfo(schedule.timezone)
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


def _schedule_time(schedule: ScheduleSetting) -> time:
    hour, minute = schedule.run_time.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def _frequency_matches(schedule: ScheduleSetting, session_date: date) -> bool:
    if schedule.frequency == "trading_daily":
        return True
    if schedule.frequency == "weekly":
        return session_date.weekday() == 4
    return False


def _market_is_open(session_date: date, calendar_mode: str) -> bool:
    timestamp = pd.Timestamp(session_date.isoformat())
    if calendar_mode == "CN":
        return exchange_calendars.get_calendar("XSHG").is_session(timestamp)
    if calendar_mode == "HK":
        return exchange_calendars.get_calendar("XHKG").is_session(timestamp)
    return exchange_calendars.get_calendar("XSHG").is_session(
        timestamp
    ) or exchange_calendars.get_calendar("XHKG").is_session(timestamp)
