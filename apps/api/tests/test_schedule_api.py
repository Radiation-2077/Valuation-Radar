from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Thread
from time import sleep

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AiRun, Instrument, JobRun, ScheduleSetting, ValuationReport
from app.services.job_lifecycle import (
    accumulate_execution_seconds,
    recover_interrupted_jobs,
)


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


def test_resume_interrupted_valuation_job(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'resume-job.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        instrument = Instrument(name="香港证券ETF", asset_type="etf")
        setup.add(instrument)
        setup.flush()
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="interrupted",
            phase="interrupted",
            idempotency_key="resume-interrupted-job",
            error="服务重启导致任务中断",
            details={
                "instrument": instrument.name,
                "failed_phase": "valuing",
                "errors": ["服务重启导致任务中断"],
            },
        )
        setup.add(job)
        setup.commit()
        job_id = job.id

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        resumed = client.post(f"/api/v1/jobs/{job_id}/resume")
        assert resumed.status_code == 202
        payload = resumed.json()
        assert payload["status"] == "queued"
        assert payload["phase"] == "queued"
        assert payload["error"] == ""
        assert payload["details"]["resume_count"] == 1
        assert "errors" not in payload["details"]
        assert "failed_phase" not in payload["details"]
        assert payload["details"]["debug_events"][-1]["message"] == (
            "任务已恢复，等待 worker 重新执行"
        )
    finally:
        app.dependency_overrides.clear()


def test_pause_and_resume_running_valuation_job(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'pause-job.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        instrument = Instrument(name="暂停测试标的")
        setup.add(instrument)
        setup.flush()
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key="pause-running-job",
            started_at=datetime.now(UTC).replace(tzinfo=None)
            - timedelta(seconds=12),
            details={
                "instrument": instrument.name,
                "execution_seconds": 30,
            },
        )
        setup.add(job)
        setup.commit()
        job_id = job.id

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        paused = client.post(f"/api/v1/jobs/{job_id}/pause")
        assert paused.status_code == 200
        payload = paused.json()
        assert payload["status"] == "paused"
        assert payload["phase"] == "paused"
        assert payload["details"]["paused_from_phase"] == "valuing"
        assert payload["details"]["execution_seconds"] >= 41
        assert payload["finished_at"] is not None

        resumed = client.post(f"/api/v1/jobs/{job_id}/resume")
        assert resumed.status_code == 202
        assert resumed.json()["status"] == "queued"
        assert resumed.json()["details"]["execution_seconds"] >= 41
        assert "paused_from_phase" not in resumed.json()["details"]
    finally:
        app.dependency_overrides.clear()


def test_delete_running_job_waits_for_worker_termination(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'delete-running-job.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        instrument = Instrument(name="删除测试标的")
        setup.add(instrument)
        setup.flush()
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key="delete-running-job",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            details={"instrument": instrument.name},
        )
        setup.add(job)
        setup.flush()
        setup.add(
            AiRun(
                job_id=job.id,
                instrument_id=instrument.id,
                status="running",
            )
        )
        setup.commit()
        job_id = job.id

    def finish_worker_termination() -> None:
        sleep(0.2)
        with Session(engine) as session:
            running = session.get(JobRun, job_id)
            assert running is not None
            running.status = "cancelled"
            running.phase = "cancelled"
            session.commit()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    worker_thread = Thread(target=finish_worker_termination)
    try:
        worker_thread.start()
        client = TestClient(app)
        deleted = client.delete(f"/api/v1/jobs/{job_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {
            "job_id": job_id,
            "deleted": True,
            "terminated": True,
        }
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404
    finally:
        worker_thread.join()
        app.dependency_overrides.clear()


def test_recover_running_jobs_after_worker_restart(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'recover-jobs.db'}")
    Base.metadata.create_all(engine)
    stdout_path = tmp_path / "codex.stdout.jsonl"
    stdout_path.write_text(
        '{"type":"thread.started","thread_id":"recoverable-thread"}\n',
        encoding="utf-8",
    )

    with Session(engine) as session:
        instrument = Instrument(name="中断测试标的")
        session.add(instrument)
        session.flush()
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key="recover-running-job",
            started_at=datetime.now(UTC).replace(tzinfo=None)
            - timedelta(seconds=20),
            details={"instrument": instrument.name},
        )
        session.add(job)
        session.flush()
        session.add(
            AiRun(
                job_id=job.id,
                instrument_id=instrument.id,
                status="running",
                metadata_json={"stdout_path": str(stdout_path)},
            )
        )
        session.commit()

        assert recover_interrupted_jobs(session) == 1
        session.refresh(job)
        assert job.status == "interrupted"
        assert job.phase == "interrupted"
        assert job.details["failed_phase"] == "valuing"
        assert job.details["interruption_kind"] == "service_restart"
        assert job.details["codex_session_id"] == "recoverable-thread"
        assert job.details["execution_seconds"] >= 19
        assert job.details["debug_events"][-1]["phase"] == "interrupted"
        ai_run = session.query(AiRun).filter_by(job_id=job.id).one()
        assert ai_run.status == "interrupted"
        assert ai_run.finished_at is not None


def test_execution_time_accumulates_across_attempts() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    job = JobRun(
        job_type="valuation_refresh",
        trigger="manual",
        scope="instrument:1",
        status="running",
        phase="valuing",
        idempotency_key="cumulative-execution-job",
        started_at=now - timedelta(seconds=15),
        details={
            "debug_events": [
                {
                    "at": "2026-10-24T16:00:00.000Z",
                    "phase": "valuing",
                    "message": "任务开始执行",
                },
                {
                    "at": "2026-10-24T16:00:20.000Z",
                    "phase": "paused",
                    "message": "已暂停",
                },
            ]
        },
    )

    assert accumulate_execution_seconds(job, now) >= 34
    job.started_at = now - timedelta(seconds=10)
    assert accumulate_execution_seconds(job, now) >= 44
    assert job.details["execution_seconds"] >= 44


def test_historical_job_derives_review_phase_from_report(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'review-phase.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        instrument = Instrument(name="历史候选标的")
        setup.add(instrument)
        setup.flush()
        report = ValuationReport(
            instrument_id=instrument.id,
            analysis_date=date(2026, 10, 25),
            schema_version="1.2",
            source="codex",
            card_sha256="reviewed-card",
            status="rejected",
        )
        setup.add(report)
        setup.flush()
        report_id = report.id
        setup.add(
            JobRun(
                job_type="valuation_refresh",
                trigger="manual",
                scope=f"instrument:{instrument.id}",
                status="succeeded",
                phase="awaiting_review",
                idempotency_key="historical-review-phase",
                details={"report_id": report.id, "instrument": instrument.name},
            )
        )
        setup.commit()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        job = client.get("/api/v1/jobs").json()["items"][0]
        assert job["phase"] == "review_rejected"
        assert job["details"]["review_status"] == "rejected"
        rejected = client.get("/api/v1/reviews/rejected").json()["items"]
        assert [item["name"] for item in rejected] == ["历史候选标的"]

        deleted = client.delete(f"/api/v1/reviews/{report_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"report_id": report_id, "deleted": True}
        assert client.get("/api/v1/reviews/rejected").json()["items"] == []
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
    stdout_path.write_text(
        "\n".join(
            [
                '{"type":"turn.started"}',
                '{"type":"item.started","item":{"type":"command_execution","command":"curl -s https://example.com"}}',
                '{"type":"item.completed","item":{"type":"agent_message","text":"行情数据已完成交叉核验"}}',
                '{"type":"turn.completed","usage":{"input_tokens":1200,"cached_input_tokens":900,"output_tokens":80,"reasoning_output_tokens":20}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
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
        assert payload["current_action"] == "Codex 执行完成"
        assert any(
            item["message"] == "行情数据已完成交叉核验"
            for item in payload["codex_events"]
        )
        assert "stdout" not in payload
        assert "stderr" not in payload
        assert payload["ai_runs"][0]["model"] == "test-model"
        assert payload["ai_runs"][0]["exit_code"] == 2
        assert payload["ai_runs"][0]["token_usage"] == {
            "input_tokens": 1200,
            "cached_input_tokens": 900,
            "output_tokens": 80,
            "reasoning_output_tokens": 20,
        }

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
