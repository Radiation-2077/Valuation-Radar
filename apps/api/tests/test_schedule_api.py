from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import ScheduleSetting


def test_schedule_and_manual_job_api(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        setup.add(ScheduleSetting(enabled=True, run_time="18:30"))
        setup.commit()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        schedule = client.get("/api/v1/schedule")
        assert schedule.status_code == 200
        assert schedule.json()["frequency"] == "trading_daily"

        patched = client.patch(
            "/api/v1/schedule",
            json={"enabled": False, "run_time": "19:15", "calendar_mode": "CN"},
        )
        assert patched.status_code == 200
        assert patched.json()["enabled"] is False
        assert patched.json()["run_time"] == "19:15"
        assert patched.json()["next_run_at"] is None

        created = client.post(
            "/api/v1/jobs",
            json={"job_type": "market_refresh", "scope": "all"},
            headers={"Idempotency-Key": "test-manual-job"},
        )
        assert created.status_code == 202
        assert created.json()["status"] == "queued"

        duplicate = client.post(
            "/api/v1/jobs",
            json={"job_type": "market_refresh", "scope": "all"},
            headers={"Idempotency-Key": "test-manual-job"},
        )
        assert duplicate.json()["id"] == created.json()["id"]

        jobs = client.get("/api/v1/jobs")
        assert jobs.status_code == 200
        assert jobs.json()["items"][0]["id"] == created.json()["id"]
    finally:
        app.dependency_overrides.clear()
