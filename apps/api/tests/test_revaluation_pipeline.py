from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.integrations.codex import CodexResult
from app.models import (
    AiRun,
    Instrument,
    JobRun,
    Listing,
    QuoteObservation,
    ValuationMarket,
    ValuationReport,
)
from app.providers.tencent import ListingRef, QuoteBatch, QuoteData
from app.services.importer import import_legacy_cards
from app.services.queries import get_ranking, get_valuation_detail
from app.services.revaluation import ValuationPaused, run_valuation_refresh
from app.services.reviews import (
    approve_review,
    list_rejected_reports,
    list_review_reports,
    reject_review,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_EXAMPLE = (
    PROJECT_ROOT
    / "schemas"
    / "value-investing"
    / "examples"
    / "card-v1.2.example.json"
)


def seed_published_contract(
    session: Session,
    directory: Path,
    settings: Settings,
) -> Instrument:
    card = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
    data_dir = directory / "seed"
    data_dir.mkdir(parents=True)
    card_path = data_dir / f"{card['name']}_{card['analysis_date']}.json"
    card_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    import_legacy_cards(session, data_dir=data_dir, settings=settings)
    instrument = session.scalar(
        select(Instrument).where(Instrument.name == card["name"])
    )
    assert instrument is not None
    return instrument


class FakeCodexExecutor:
    def __init__(
        self,
        settings: Settings,
        missing: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self.settings = settings
        self.missing = missing or []
        self.warnings = warnings or []
        self.last_prompt = ""
        self.last_evidence: dict = {}
        self.resume_session_ids: list[str | None] = []

    def run(
        self,
        cwd: Path,
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
        resume_session_id: str | None = None,
    ) -> CodexResult:
        del output_schema
        self.resume_session_ids.append(resume_session_id)
        self.last_prompt = prompt
        self.last_evidence = json.loads(
            (cwd / "evidence.json").read_text(encoding="utf-8")
        )
        previous_card = json.loads(
            (cwd / "previous_card.json").read_text(encoding="utf-8")
        )
        card = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
        card["name"] = previous_card["name"]
        card["codes"] = previous_card.get("codes", card["codes"])
        previous_markets = {
            market["market"]: market
            for market in previous_card.get("markets") or []
        }
        for market in card["markets"]:
            previous = previous_markets.get(market["market"])
            if previous:
                market["code"] = previous["code"]
                market["currency"] = previous.get("currency", market["currency"])
        analysis_date = datetime.now(ZoneInfo(self.settings.timezone)).date()
        card["analysis_date"] = analysis_date.isoformat()
        card["generated_at"] = datetime.now(ZoneInfo(self.settings.timezone)).isoformat()
        card["conclusion"]["verdict"] = {
            "code": "watch",
            "label": "观望等待",
        }
        card["missing"] = list(self.missing)
        card_path = cwd / "data" / f"{card['name']}_{analysis_date.isoformat()}.json"
        card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "data_card_path": str(card_path),
                    "summary": "fake",
                    "warnings": list(self.warnings),
                }
            ),
            encoding="utf-8",
        )
        stdout_path = cwd / "fake.stdout"
        stderr_path = cwd / "fake.stderr"
        stdout_path.write_text("{}", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return CodexResult(
            exit_code=0,
            version="codex-fake 1.0",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            manifest_path=manifest_path,
            thread_id="fake-thread-1",
        )


class FailingCodexExecutor:
    def run(
        self,
        cwd: Path,
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
        resume_session_id: str | None = None,
    ) -> CodexResult:
        del prompt, output_schema, manifest_path, resume_session_id
        stdout_path = cwd / "failed.stdout"
        stderr_path = cwd / "failed.stderr"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("sandbox and approval options conflict", encoding="utf-8")
        return CodexResult(
            exit_code=2,
            version="codex-fake 1.0",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            manifest_path=cwd / "missing-manifest.json",
        )


class PausingThenResumingCodexExecutor(FakeCodexExecutor):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.checkpoint_survived = False

    def run(
        self,
        cwd: Path,
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
        resume_session_id: str | None = None,
    ) -> CodexResult:
        if resume_session_id is None:
            self.resume_session_ids.append(None)
            (cwd / "checkpoint.txt").write_text("keep me", encoding="utf-8")
            stdout_path = cwd / "paused.stdout"
            stderr_path = cwd / "paused.stderr"
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("paused", encoding="utf-8")
            return CodexResult(
                exit_code=-3,
                version="codex-fake 1.0",
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                manifest_path=manifest_path,
                paused=True,
                thread_id="fake-thread-1",
            )
        self.checkpoint_survived = (cwd / "checkpoint.txt").read_text(
            encoding="utf-8"
        ) == "keep me"
        return super().run(
            cwd,
            prompt,
            output_schema,
            manifest_path,
            resume_session_id,
        )


class FixedRevaluationQuoteProvider:
    def fetch(self, listings: list[ListingRef]) -> QuoteBatch:
        return QuoteBatch(
            quotes=[
                QuoteData(
                    listing_id=listing.listing_id,
                    observed_at=datetime(2026, 10, 25, 8, 0, tzinfo=UTC).replace(
                        tzinfo=None
                    ),
                    quote_date=date(2026, 10, 25),
                    price=10.0,
                    previous_close=9.8,
                    change_pct=2.0,
                    pe=8.0,
                    pb=1.2,
                    source_name="测试行情",
                    raw={},
                )
                for listing in listings
            ]
        )


class FailingRevaluationQuoteProvider:
    def fetch(self, listings: list[ListingRef]) -> QuoteBatch:
        del listings
        return QuoteBatch(errors=["测试行情源不可用"])


def test_codex_candidate_requires_review_before_ranking(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )

    with Session(engine, autoflush=False) as session:
        instrument = seed_published_contract(session, tmp_path, settings)
        old_market_id, old_market_name = session.execute(
            select(ValuationMarket.id, Listing.market)
            .join(ValuationReport, ValuationReport.id == ValuationMarket.report_id)
            .join(Listing, Listing.id == ValuationMarket.listing_id)
            .where(ValuationReport.instrument_id == instrument.id)
            .order_by(ValuationReport.analysis_date, ValuationReport.revision)
            .limit(1)
        ).one()
        original_verdict = instrument.verdict
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="running",
            idempotency_key="candidate-test",
        )
        session.add(job)
        session.commit()

        executor = FakeCodexExecutor(settings)
        report = run_valuation_refresh(
            session,
            job,
            settings,
            executor=executor,
            quote_provider=FixedRevaluationQuoteProvider(),
        )
        assert report.status == "needs_review"
        assert report.source == "codex"
        assert report.schema_version == "1.2"
        assert session.get(Instrument, instrument.id).verdict == original_verdict  # type: ignore[union-attr]
        assert [item.id for item in list_review_reports(session)] == [report.id]
        candidate_detail = get_valuation_detail(session, report.markets[0].id)
        assert candidate_detail.latest_valuation_market_id == report.markets[0].id
        session.refresh(job)
        assert executor.last_evidence["listings"][0]["latest_quote"]["price"] == 10.0
        assert "必须继续使用公开接口联网获取" in executor.last_prompt
        assert (settings.staging_dir / f"job-{job.id}" / instrument.name / "common").is_dir()
        assert any(
            "Codex 新会话" in event["message"]
            for event in job.details["debug_events"]
        )
        assert job.details["codex_session_id"] == "fake-thread-1"

        published = approve_review(session, report.id)
        assert published.status == "published"
        session.refresh(job)
        assert job.phase == "review_approved"
        assert job.details["review_status"] == "published"
        assert job.details["review_required"] is False
        assert any(
            event["phase"] == "review_approved"
            for event in job.details["debug_events"]
        )
        assert session.get(Instrument, instrument.id).verdict == "观望等待"  # type: ignore[union-attr]
        assert session.query(ValuationReport).filter_by(status="needs_review").count() == 0
        assert session.query(ValuationReport).filter_by(status="published").count() > 0
        ranking = get_ranking(session, profile="balanced")
        ranked = next(
            item
            for item in ranking.main_board
            if item.name == instrument.name and item.market == "A"
        )
        assert ranked.report_id == published.id
        assert ranked.valuation_market_id in {market.id for market in published.markets}
        detail = get_valuation_detail(session, published.markets[0].id)
        assert detail.report_detail["sections"][0]["blocks"][0]["type"] == "gauges"
        old_detail = get_valuation_detail(session, old_market_id)
        assert old_detail.valuation_market_id == old_market_id
        latest_market_id = next(
            market.id
            for market in published.markets
            if market.listing.market == old_market_name
        )
        assert old_detail.latest_valuation_market_id == latest_market_id


def test_revaluation_resumes_saved_codex_session_and_workspace(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'session-resume.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )

    with Session(engine, autoflush=False) as session:
        instrument = seed_published_contract(session, tmp_path, settings)
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key="resume-session-test",
        )
        session.add(job)
        session.commit()
        executor = PausingThenResumingCodexExecutor(settings)

        with pytest.raises(ValuationPaused):
            run_valuation_refresh(
                session,
                job,
                settings,
                executor=executor,
                quote_provider=FixedRevaluationQuoteProvider(),
            )

        session.refresh(job)
        assert job.status == "paused"
        assert job.details["codex_session_id"] == "fake-thread-1"
        job.status = "running"
        session.commit()

        report = run_valuation_refresh(
            session,
            job,
            settings,
            executor=executor,
            quote_provider=FixedRevaluationQuoteProvider(),
        )

        assert report.status == "needs_review"
        assert executor.resume_session_ids == [None, "fake-thread-1"]
        assert executor.checkpoint_survived is True
        assert "从断点继续" in executor.last_prompt


def test_rejecting_candidate_updates_job_stage(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate-reject.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )
    with Session(engine, autoflush=False) as session:
        instrument = seed_published_contract(session, tmp_path, settings)
        report = session.scalar(
            select(ValuationReport)
            .where(ValuationReport.instrument_id == instrument.id)
            .order_by(ValuationReport.id)
            .limit(1)
        )
        assert report is not None
        report.status = "needs_review"
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="succeeded",
            phase="awaiting_review",
            idempotency_key="candidate-rejected-review",
            details={"instrument": instrument.name},
        )
        session.add(job)
        session.flush()
        session.add(
            AiRun(
                job_id=job.id,
                instrument_id=instrument.id,
                status="succeeded",
                metadata_json={"report_id": report.id},
            )
        )
        session.commit()

        rejected = reject_review(session, report.id)
        assert rejected.status == "rejected"
        assert report.id in {
            item.id for item in list_rejected_reports(session)
        }
        session.refresh(job)
        assert job.phase == "review_rejected"
        assert job.details["review_status"] == "rejected"
        assert job.details["review_required"] is False
        assert any(
            event["phase"] == "review_rejected"
            for event in job.details["debug_events"]
        )


def test_codex_failure_keeps_published_valuation(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate-failure.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )

    with Session(engine) as session:
        instrument = seed_published_contract(session, tmp_path, settings)
        original_verdict = instrument.verdict
        published_before = session.query(ValuationReport).filter_by(
            instrument_id=instrument.id,
            status="published",
        ).count()
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key="candidate-failure-test",
        )
        session.add(job)
        session.commit()

        with pytest.raises(RuntimeError, match="Codex 退出码 2"):
            run_valuation_refresh(
                session,
                job,
                settings,
                executor=FailingCodexExecutor(),
                quote_provider=FixedRevaluationQuoteProvider(),
            )

        session.refresh(instrument)
        assert instrument.verdict == original_verdict
        assert session.query(ValuationReport).filter_by(
            instrument_id=instrument.id,
            status="published",
        ).count() == published_before
        assert session.query(ValuationReport).filter_by(status="needs_review").count() == 0
        failed_run = session.query(AiRun).filter_by(job_id=job.id).one()
        assert failed_run.status == "rejected"
        assert failed_run.exit_code == 2
        assert "sandbox and approval options conflict" in failed_run.stderr
        session.refresh(job)
        assert any(
            "重估失败" in event["message"]
            for event in job.details["debug_events"]
        )


def test_valuation_stops_before_codex_when_quote_refresh_fails(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'quote-failure.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )
    with Session(engine, autoflush=False) as session:
        instrument = seed_published_contract(session, tmp_path, settings)
        for quote in session.query(QuoteObservation):
            session.delete(quote)
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key="quote-failure",
        )
        session.add(job)
        session.commit()

        with pytest.raises(RuntimeError, match="自动行情刷新失败"):
            run_valuation_refresh(
                session,
                job,
                settings,
                executor=FakeCodexExecutor(settings),
                quote_provider=FailingRevaluationQuoteProvider(),
            )
        assert session.query(AiRun).filter_by(job_id=job.id).count() == 0


@pytest.mark.parametrize(
    ("missing", "warnings", "message"),
    [
        (["ROE 不可获取"], [], "缺失数据"),
        ([], ["行情源联网失败"], "存在警告"),
    ],
)
def test_codex_rejects_incomplete_or_warned_output(
    tmp_path: Path,
    missing: list[str],
    warnings: list[str],
    message: str,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate-strict.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )
    with Session(engine) as session:
        instrument = seed_published_contract(session, tmp_path, settings)
        published_before = session.query(ValuationReport).filter_by(
            instrument_id=instrument.id,
            status="published",
        ).count()
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key=f"strict-{len(missing)}-{len(warnings)}",
        )
        session.add(job)
        session.commit()

        with pytest.raises(RuntimeError, match=message):
            run_valuation_refresh(
                session,
                job,
                settings,
                executor=FakeCodexExecutor(
                    settings,
                    missing=missing,
                    warnings=warnings,
                ),
                quote_provider=FixedRevaluationQuoteProvider(),
            )

        assert session.query(ValuationReport).filter_by(status="needs_review").count() == 0
        assert session.query(ValuationReport).filter_by(
            instrument_id=instrument.id,
            status="published",
        ).count() == published_before
        assert session.query(AiRun).filter_by(job_id=job.id).one().status == "rejected"
