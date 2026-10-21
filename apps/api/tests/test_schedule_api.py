from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AiRun, Instrument, JobRun, ScheduleSetting


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


def test_job_debug_and_clear_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs-api.db'}")
    Base.metadata.create_all(engine)
    storage = tmp_path / "storage"
    storage.mkdir()
    stdout_path = storage / "codex.stdout.jsonl"
    stderr_path = storage / "codex.stderr.log"
    stdout_path.write_text('{"type":"item.completed"}\n', encoding="utf-8")
    stderr_path.write_text("live stderr\n", encoding="utf-8")
    settings = Settings(storage_root=storage)

    with Session(engine) as setup:
        instrument = Instrument(name="调试标的")
        active = JobRun(
            job_type="market_refresh",
            trigger="manual",
            scope="all",
            status="running",
            phase="fetching",
            idempotency_key="active-job",
        )
        debug_job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope="instrument:1",
            status="failed",
            phase="validating",
            idempotency_key="debug-job",
            error="候选校验失败",
            details={
                "debug_events": [
                    {
                        "at": "2026-10-22T01:00:00.000Z",
                        "phase": "valuing",
                        "message": "Codex 子进程已启动",
                    }
                ]
            },
        )
        setup.add_all([instrument, active, debug_job])
        setup.flush()
        setup.add(
            AiRun(
                job_id=debug_job.id,
                instrument_id=instrument.id,
                status="rejected",
                model="test-model",
                cli_version="codex-test",
                exit_code=2,
                prompt_path=str(storage / "prompt.md"),
                output_path=str(storage / "manifest.json"),
                stderr="候选校验失败",
                metadata_json={
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                },
                started_at=datetime.now(UTC).replace(tzinfo=None),
                finished_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        setup.commit()
        debug_job_id = debug_job.id
        active_job_id = active.id

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("app.api.v1.router.get_settings", lambda: settings)
    try:
        client = TestClient(app)

        blocked = client.delete("/api/v1/jobs")
        assert blocked.status_code == 409
        assert "不能清除" in blocked.json()["detail"]["message"]

        debug = client.get(f"/api/v1/jobs/{debug_job_id}/debug")
        assert debug.status_code == 200
        payload = debug.json()
        assert payload["events"][0]["message"] == "Codex 子进程已启动"
        assert payload["stdout"] == '{"type":"item.completed"}\n'
        assert payload["stderr"] == "live stderr\n"
        assert payload["ai_runs"][0]["model"] == "test-model"
        assert payload["ai_runs"][0]["exit_code"] == 2

        with Session(engine) as session:
            active = session.get(JobRun, active_job_id)
            assert active is not None
            active.status = "failed"
            active.phase = "failed"
            session.commit()

        cleared = client.delete("/api/v1/jobs")
        assert cleared.status_code == 200
        assert cleared.json()["deleted"] == 2
        assert client.get("/api/v1/jobs").json()["items"] == []
    finally:
        app.dependency_overrides.clear()
