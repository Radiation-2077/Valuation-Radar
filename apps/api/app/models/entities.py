from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(20), default="stock")
    path: Mapped[str] = mapped_column(String(20), default="stable")
    industry: Mapped[str] = mapped_column(String(100), default="")
    cycle_stage: Mapped[str] = mapped_column(String(200), default="")
    cycle_position: Mapped[float | None] = mapped_column(Float)
    quality_rating: Mapped[int] = mapped_column(Integer, default=0)
    quality_label: Mapped[str] = mapped_column(String(50), default="")
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    moat: Mapped[str] = mapped_column(String(20), default="")
    gate_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_reason: Mapped[str] = mapped_column(Text, default="")
    verdict: Mapped[str] = mapped_column(String(20), default="")
    thesis: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(20), default="中")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    archive_reason: Mapped[str] = mapped_column(String(200), default="")

    listings: Mapped[list[Listing]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list[ValuationReport]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )


class Listing(TimestampMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("market", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    market: Mapped[str] = mapped_column(String(10), index=True)
    code: Mapped[str] = mapped_column(String(30), index=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    instrument: Mapped[Instrument] = relationship(back_populates="listings")
    market_snapshots: Mapped[list[ValuationMarket]] = relationship(back_populates="listing")
    quote_observations: Mapped[list[QuoteObservation]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
    )


class ValuationReport(TimestampMixin, Base):
    __tablename__ = "valuation_reports"
    __table_args__ = (UniqueConstraint("instrument_id", "analysis_date", "revision"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    analysis_date: Mapped[date] = mapped_column(Date, index=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    source: Mapped[str] = mapped_column(String(30), default="legacy")
    macro: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    risks: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    raw_card: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    card_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="published", index=True)

    instrument: Mapped[Instrument] = relationship(back_populates="reports")
    markets: Mapped[list[ValuationMarket]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )


class ValuationMarket(TimestampMixin, Base):
    __tablename__ = "valuation_markets"
    __table_args__ = (UniqueConstraint("report_id", "listing_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("valuation_reports.id", ondelete="CASCADE"))
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    price: Mapped[float] = mapped_column(Float)
    price_date: Mapped[date] = mapped_column(Date)
    fair_low: Mapped[float] = mapped_column(Float)
    fair_mid: Mapped[float] = mapped_column(Float)
    fair_high: Mapped[float] = mapped_column(Float)
    safety_margin_pct: Mapped[float | None] = mapped_column(Float)
    pe: Mapped[float | None] = mapped_column(Float)
    pb: Mapped[float | None] = mapped_column(Float)
    dividend_yield_after_tax: Mapped[float | None] = mapped_column(Float)
    percentile: Mapped[float | None] = mapped_column(Float)
    gauges: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expected_return: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    downside: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    position: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verdict: Mapped[str] = mapped_column(String(20), default="")

    report: Mapped[ValuationReport] = relationship(back_populates="markets")
    listing: Mapped[Listing] = relationship(back_populates="market_snapshots")


class RankingRun(Base):
    __tablename__ = "ranking_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime, index=True)
    profile: Mapped[str] = mapped_column(String(30), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(20), default="1.0")
    config_hash: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), default="published")

    entries: Mapped[list[RankingEntry]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class RankingEntry(Base):
    __tablename__ = "ranking_entries"
    __table_args__ = (UniqueConstraint("run_id", "valuation_market_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ranking_runs.id", ondelete="CASCADE"))
    valuation_market_id: Mapped[int] = mapped_column(
        ForeignKey("valuation_markets.id", ondelete="CASCADE")
    )
    rank: Mapped[int | None] = mapped_column(Integer)
    band: Mapped[str] = mapped_column(String(2), default="D")
    score: Mapped[float | None] = mapped_column(Float)
    score_margin: Mapped[float | None] = mapped_column(Float)
    score_base: Mapped[float | None] = mapped_column(Float)
    score_risk: Mapped[float | None] = mapped_column(Float)
    score_stability: Mapped[float | None] = mapped_column(Float)
    effective_safety_margin_pct: Mapped[float | None] = mapped_column(Float)
    current_price: Mapped[float | None] = mapped_column(Float)
    base_income: Mapped[float | None] = mapped_column(Float)
    expected_total: Mapped[float | None] = mapped_column(Float)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float)
    risk_adjusted_ratio: Mapped[float | None] = mapped_column(Float)
    value_reliance: Mapped[float] = mapped_column(Float, default=0)
    excluded_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)

    run: Mapped[RankingRun] = relationship(back_populates="entries")
    valuation_market: Mapped[ValuationMarket] = relationship()


class QuoteObservation(Base):
    __tablename__ = "quote_observations"
    __table_args__ = (UniqueConstraint("listing_id", "source", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    quote_date: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[float] = mapped_column(Float)
    previous_close: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    pe: Mapped[float | None] = mapped_column(Float)
    pb: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(30))
    source_name: Mapped[str] = mapped_column(String(100), default="")
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    listing: Mapped[Listing] = relationship(back_populates="quote_observations")


class MacroObservation(Base):
    __tablename__ = "macro_observations"
    __table_args__ = (UniqueConstraint("key", "source", "as_of"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), index=True)
    as_of: Mapped[date] = mapped_column(Date, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="")
    source: Mapped[str] = mapped_column(String(200))
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ScheduleSetting(TimestampMixin, Base):
    __tablename__ = "schedule_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    frequency: Mapped[str] = mapped_column(String(30), default="trading_daily")
    run_time: Mapped[str] = mapped_column(String(5), default="18:30")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Shanghai")
    calendar_mode: Mapped[str] = mapped_column(String(20), default="CN")
    scope: Mapped[str] = mapped_column(String(20), default="all")
    revaluation_mode: Mapped[str] = mapped_column(String(30), default="weekly_event")
    publish_mode: Mapped[str] = mapped_column(String(30), default="review_exceptions")
    stale_after_days: Mapped[int] = mapped_column(Integer, default=7)


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(30), index=True)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    scope: Mapped[str] = mapped_column(String(50), default="all")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(30), default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(200))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AiRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    cli_version: Mapped[str] = mapped_column(String(100), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    prompt_path: Mapped[str] = mapped_column(String(500), default="")
    output_path: Mapped[str] = mapped_column(String(500), default="")
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stderr: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
