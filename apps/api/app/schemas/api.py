from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProfileOut(BaseModel):
    code: str
    label: str
    description: str
    weights: dict[str, float]


class MetaResponse(BaseModel):
    profiles: list[ProfileOut]
    default_profile: str
    algorithm_version: str


class FreshnessOut(BaseModel):
    ranking_as_of: datetime
    latest_analysis_date: date | None
    latest_price_date: date | None
    stale_after_days: int
    stale_units: int
    status: str


class ScoreOut(BaseModel):
    margin: float | None = None
    base: float | None = None
    risk: float | None = None
    stability: float | None = None
    total: float | None = None
    band: str = "D"


class RankingItemOut(BaseModel):
    valuation_market_id: int
    report_id: int
    instrument_id: int
    name: str
    market: str
    code: str
    currency: str
    industry: str
    path: str
    analysis_date: date
    stale_days: int
    price: float
    price_date: date
    fair_low: float
    fair_mid: float
    fair_high: float
    safety_margin_pct: float | None
    expected_return: dict[str, Any]
    max_drawdown_pct: float | None
    verdict: str
    thesis: str
    confidence: str
    rank: int | None
    score: ScoreOut
    base_income: float | None
    risk_adjusted_ratio: float | None
    value_reliance: float
    risk_flags: list[str]
    excluded_reasons: list[str]
    is_etf: bool


class RankingResponse(BaseModel):
    profile: str
    profile_label: str
    algorithm_version: str
    main_board: list[RankingItemOut]
    etfs: list[RankingItemOut]
    excluded: list[RankingItemOut]
    top_three: list[RankingItemOut]
    counts: dict[str, int]
    freshness: FreshnessOut
    available_industries: list[str]
    available_paths: list[str]
    available_markets: list[str]


class QualityOut(BaseModel):
    rating: int
    label: str
    score: float
    moat: str
    gate_pass: bool
    gate_reason: str


class CycleOut(BaseModel):
    stage: str
    position: float | None


class MarketSummaryOut(BaseModel):
    valuation_market_id: int
    market: str
    code: str
    currency: str
    price: float
    fair_mid: float
    safety_margin_pct: float | None
    verdict: str


class ValuationDetailOut(BaseModel):
    valuation_market_id: int
    report_id: int
    instrument_id: int
    name: str
    market: str
    code: str
    currency: str
    asset_type: str
    path: str
    industry: str
    analysis_date: date
    generated_at: datetime | None
    price_date: date
    stale_days: int
    quality: QualityOut
    cycle: CycleOut
    conclusion: dict[str, str]
    price: float
    baseline_price: float
    current_price: float
    fair_low: float
    fair_mid: float
    fair_high: float
    safety_margin_pct: float | None
    effective_safety_margin_pct: float | None
    valuation: dict[str, float | None]
    gauges: dict[str, Any]
    expected_return: dict[str, Any]
    downside: dict[str, Any]
    position: dict[str, Any]
    verdict: str
    score: ScoreOut
    risks: list[str]
    missing: list[str] = Field(default_factory=list)
    notes: str
    risk_flags: list[str]
    excluded_reasons: list[str]
    same_company: list[MarketSummaryOut]


class InstrumentOut(BaseModel):
    id: int
    name: str
    asset_type: str
    path: str
    industry: str
    verdict: str
    enabled: bool
    markets: list[str]
    latest_analysis_date: date | None


class InstrumentListOut(BaseModel):
    items: list[InstrumentOut]


class ScheduleOut(BaseModel):
    enabled: bool
    frequency: str
    run_time: str
    timezone: str
    calendar_mode: str
    scope: str
    revaluation_mode: str
    publish_mode: str
    stale_after_days: int
    next_run_at: datetime | None
    updated_at: datetime


class SchedulePatch(BaseModel):
    enabled: bool | None = None
    frequency: Literal["trading_daily", "weekly", "manual"] | None = None
    run_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    calendar_mode: Literal["CN", "HK", "ANY"] | None = None
    scope: Literal["all"] | None = None
    revaluation_mode: Literal["weekly_event", "weekly", "trading_daily", "off"] | None = None
    publish_mode: Literal["review_all", "review_exceptions", "auto"] | None = None
    stale_after_days: int | None = Field(default=None, ge=1, le=90)


class JobOut(BaseModel):
    id: int
    job_type: str
    trigger: str
    scope: str
    status: str
    phase: str
    scheduled_for: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str
    details: dict[str, Any]
    created_at: datetime


class JobCreate(BaseModel):
    job_type: Literal["market_refresh"] = "market_refresh"
    scope: Literal["all"] = "all"


class JobListOut(BaseModel):
    items: list[JobOut]


class ReviewMarketOut(BaseModel):
    valuation_market_id: int
    market: str
    code: str
    currency: str
    price: float
    fair_mid: float
    verdict: str


class ReviewOut(BaseModel):
    report_id: int
    instrument_id: int
    name: str
    analysis_date: date
    generated_at: datetime | None
    thesis: str
    confidence: str
    markets: list[ReviewMarketOut]


class ReviewListOut(BaseModel):
    items: list[ReviewOut]


class ReviewDecisionOut(BaseModel):
    report_id: int
    status: str
    ranking_rebuilt: bool
