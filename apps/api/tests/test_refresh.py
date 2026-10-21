from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import worker
from app.core.config import Settings
from app.db.base import Base
from app.models import Instrument, JobRun, Listing, QuoteObservation
from app.providers.tencent import ListingRef, QuoteBatch, QuoteData
from app.services.refresh import RefreshSummary, refresh_market_data

OBSERVED_AT = datetime(2026, 10, 21, 8, 0, tzinfo=UTC).replace(tzinfo=None)


class FixedQuoteProvider:
    def __init__(self, errors: list[str] | None = None) -> None:
        self.errors = errors or []

    def fetch(self, listings: list[ListingRef]) -> QuoteBatch:
        quotes = [
            QuoteData(
                listing_id=listing.listing_id,
                observed_at=OBSERVED_AT,
                quote_date=date(2026, 10, 21),
                price=10.0,
                previous_close=9.8,
                change_pct=2.04,
                pe=8.0,
                pb=1.2,
                source_name="测试标的",
                raw={},
            )
            for listing in listings
        ]
        return QuoteBatch(quotes=quotes, errors=list(self.errors))


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'refresh.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    instrument = Instrument(name="测试标的")
    instrument.listings = [Listing(market="A", code="600000.SH", currency="CNY")]
    session.add(instrument)
    session.commit()
    return session


def test_refresh_reuses_ranking_when_quote_is_unchanged(tmp_path: Path) -> None:
    phases: list[str] = []
    settings = Settings(legacy_common_dir=tmp_path / "missing-common")

    with _session(tmp_path) as session:
        first = refresh_market_data(
            session,
            settings,
            provider=FixedQuoteProvider(),
            on_phase=phases.append,
        )
        session.commit()
        second = refresh_market_data(
            session,
            settings,
            provider=FixedQuoteProvider(),
            on_phase=phases.append,
        )

        assert first.quotes_fetched == 1
        assert first.quotes_saved == 1
        assert first.quotes_unchanged == 0
        assert second.quotes_fetched == 1
        assert second.quotes_saved == 0
        assert second.quotes_unchanged == 1
        assert second.ranking_runs == 0
        assert second.ranking_reused is True
        assert second.latest_quote_at == OBSERVED_AT
        assert session.query(QuoteObservation).count() == 1
        assert phases == [
            "saving_quotes",
            "loading_macro",
            "rebuilding_ranking",
            "saving_quotes",
            "loading_macro",
            "finalizing",
        ]


def test_worker_treats_unchanged_quotes_as_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'worker-success.db'}")
    Base.metadata.create_all(engine)
    session_factory = worker_session_factory(engine)
    with session_factory() as session:
        session.add(_queued_market_job())
        session.commit()

    def fake_refresh(
        session: Session,
        settings: Settings,
        on_phase: Callable[[str], None] | None = None,
    ) -> RefreshSummary:
        del session, settings
        if on_phase:
            on_phase("finalizing")
        return RefreshSummary(
            listings=29,
            quotes_fetched=29,
            quotes_saved=0,
            quotes_unchanged=29,
            quote_errors=[],
            macro_observations=0,
            ranking_runs=0,
            ranking_reused=True,
            latest_quote_at=OBSERVED_AT,
        )

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "refresh_market_data", fake_refresh)
    monkeypatch.setattr(worker, "get_settings", lambda: Settings())

    assert worker.process_next_job() is True

    with session_factory() as session:
        job = session.query(JobRun).one()
        assert job.status == "succeeded"
        assert job.phase == "completed"
        details = dict(job.details)
        events = details.pop("debug_events")
        assert details == {
            "listings": 29,
            "quotes_fetched": 29,
            "quotes_saved": 0,
            "quotes_unchanged": 29,
            "macro_observations": 0,
            "ranking_runs": 0,
            "ranking_reused": True,
            "latest_quote_at": "2026-10-21T08:00:00",
            "errors": [],
        }
        assert [event["phase"] for event in events] == [
            "fetching",
            "finalizing",
            "completed",
        ]


def test_worker_fails_only_when_no_valid_quote_is_fetched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'worker-failure.db'}")
    Base.metadata.create_all(engine)
    session_factory = worker_session_factory(engine)
    with session_factory() as session:
        session.add(_queued_market_job())
        session.commit()

    provider_error = "腾讯批量行情请求失败：连接超时"

    def fake_refresh(
        session: Session,
        settings: Settings,
        on_phase: Callable[[str], None] | None = None,
    ) -> RefreshSummary:
        del session, settings
        if on_phase:
            on_phase("finalizing")
        return RefreshSummary(
            listings=29,
            quotes_fetched=0,
            quotes_saved=0,
            quotes_unchanged=0,
            quote_errors=[provider_error],
            macro_observations=0,
            ranking_runs=0,
            ranking_reused=True,
            latest_quote_at=None,
        )

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "refresh_market_data", fake_refresh)
    monkeypatch.setattr(worker, "get_settings", lambda: Settings())

    assert worker.process_next_job() is True

    with session_factory() as session:
        job = session.query(JobRun).one()
        assert job.status == "failed"
        assert job.phase == "fetching"
        assert provider_error in job.error
        assert job.details["failed_phase"] == "fetching"
        assert job.details["quotes_fetched"] == 0
        assert provider_error in job.details["errors"]


def test_worker_marks_partial_when_some_quotes_are_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'worker-partial.db'}")
    Base.metadata.create_all(engine)
    session_factory = worker_session_factory(engine)
    with session_factory() as session:
        session.add(_queued_market_job())
        session.commit()

    provider_error = "第二批行情请求失败"

    def fake_refresh(
        session: Session,
        settings: Settings,
        on_phase: Callable[[str], None] | None = None,
    ) -> RefreshSummary:
        del session, settings, on_phase
        return RefreshSummary(
            listings=29,
            quotes_fetched=20,
            quotes_saved=5,
            quotes_unchanged=15,
            quote_errors=[provider_error],
            macro_observations=0,
            ranking_runs=3,
            ranking_reused=False,
            latest_quote_at=OBSERVED_AT,
        )

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "refresh_market_data", fake_refresh)
    monkeypatch.setattr(worker, "get_settings", lambda: Settings())

    assert worker.process_next_job() is True

    with session_factory() as session:
        job = session.query(JobRun).one()
        assert job.status == "partial"
        assert job.details["quotes_saved"] == 5
        assert job.details["errors"] == [provider_error]


def worker_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _queued_market_job() -> JobRun:
    return JobRun(
        job_type="market_refresh",
        trigger="manual",
        scope="all",
        status="queued",
        phase="queued",
        idempotency_key="worker-test",
    )
