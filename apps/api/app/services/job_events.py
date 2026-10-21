from __future__ import annotations

from datetime import UTC, datetime

from app.models import JobRun

MAX_DEBUG_EVENTS = 200


def append_job_event(job: JobRun, phase: str, message: str) -> None:
    details = dict(job.details or {})
    events = details.get("debug_events")
    debug_events = list(events) if isinstance(events, list) else []
    debug_events.append(
        {
            "at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "phase": phase,
            "message": message,
        }
    )
    details["debug_events"] = debug_events[-MAX_DEBUG_EVENTS:]
    job.details = details
    job.phase = phase
