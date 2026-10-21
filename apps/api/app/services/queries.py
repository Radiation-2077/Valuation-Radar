from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.scoring import (
    DEFAULT_PROFILE,
    PROFILES,
    context_from_card,
    effective_margin,
    score_context,
)
from app.models import (
    Instrument,
    Listing,
    QuoteObservation,
    RankingEntry,
    RankingRun,
    ScheduleSetting,
    ValuationMarket,
    ValuationReport,
)
from app.schemas.api import (
    CycleOut,
    FreshnessOut,
    InstrumentListOut,
    InstrumentOut,
    MarketSummaryOut,
    QualityOut,
    RankingItemOut,
    RankingResponse,
    ScoreOut,
    ValuationDetailOut,
)
from app.services.ranking import latest_run, stale_days


def get_ranking(
    session: Session,
    profile: str = DEFAULT_PROFILE,
    market: str | None = None,
    path: str | None = None,
    industry: str | None = None,
) -> RankingResponse:
    if profile not in PROFILES:
        raise HTTPException(status_code=422, detail={"message": f"未知风险偏好：{profile}"})
    run = latest_run(session, profile)
    if run is None:
        raise HTTPException(status_code=503, detail={"message": "尚无可用排名，请先导入数据"})

    entries = (
        session.scalars(
            select(RankingEntry)
            .where(RankingEntry.run_id == run.id)
            .options(
                selectinload(RankingEntry.valuation_market)
                .selectinload(ValuationMarket.report)
                .selectinload(ValuationReport.instrument),
                selectinload(RankingEntry.valuation_market).selectinload(ValuationMarket.listing),
            )
        )
        .unique()
        .all()
    )
    stale_after = _stale_after_days(session)
    listing_ids = [entry.valuation_market.listing_id for entry in entries]
    quote_rows = (
        session.scalars(
            select(QuoteObservation)
            .where(QuoteObservation.listing_id.in_(listing_ids))
            .order_by(QuoteObservation.observed_at.desc(), QuoteObservation.id.desc())
        ).all()
        if listing_ids
        else []
    )
    latest_quotes: dict[int, QuoteObservation] = {}
    for quote in quote_rows:
        latest_quotes.setdefault(quote.listing_id, quote)
    items = [
        _item_from_entry(entry, stale_after, latest_quotes.get(entry.valuation_market.listing_id))
        for entry in entries
    ]
    all_items = list(items)
    items = [
        item
        for item in items
        if (not market or item.market == market)
        and (not path or item.path == path)
        and (not industry or item.industry == industry)
    ]
    main_board = sorted(
        [item for item in items if not item.excluded_reasons and not item.is_etf],
        key=lambda item: (item.rank is None, item.rank or 999, -(item.score.total or 0)),
    )
    etfs = sorted(
        [item for item in items if not item.excluded_reasons and item.is_etf],
        key=lambda item: -(item.score.total or 0),
    )
    excluded = sorted(
        [item for item in items if item.excluded_reasons],
        key=lambda item: (-(item.score.total or 0), item.name, item.market),
    )
    stale_units = sum(1 for item in all_items if item.stale_days > stale_after)
    latest_analysis = max((item.analysis_date for item in all_items), default=None)
    price_dates = []
    for entry in entries:
        latest_quote = latest_quotes.get(entry.valuation_market.listing_id)
        price_dates.append(
            latest_quote.quote_date
            if latest_quote is not None
            else entry.valuation_market.price_date
        )
    latest_price = max(price_dates, default=None)
    freshness_status = (
        "stale" if latest_analysis and stale_days(latest_analysis) > stale_after else "current"
    )
    if stale_units and freshness_status == "current":
        freshness_status = "mixed"

    profile_definition = PROFILES[profile]
    main_count = len([item for item in all_items if not item.excluded_reasons and not item.is_etf])
    etf_count = len([item for item in all_items if not item.excluded_reasons and item.is_etf])
    excluded_count = len([item for item in all_items if item.excluded_reasons])
    return RankingResponse(
        profile=profile,
        profile_label=profile_definition.label,
        algorithm_version=run.algorithm_version,
        main_board=main_board,
        etfs=etfs,
        excluded=excluded,
        top_three=main_board[:3],
        counts={
            "all": len(all_items),
            "main_board": main_count,
            "etfs": etf_count,
            "excluded": excluded_count,
            "stale": stale_units,
        },
        freshness=FreshnessOut(
            ranking_as_of=run.as_of,
            latest_analysis_date=latest_analysis,
            latest_price_date=latest_price,
            stale_after_days=stale_after,
            stale_units=stale_units,
            status=freshness_status,
        ),
        available_industries=sorted({item.industry for item in all_items if item.industry}),
        available_paths=sorted({item.path for item in all_items if item.path}),
        available_markets=sorted({item.market for item in all_items if item.market}),
    )


def get_valuation_detail(
    session: Session,
    valuation_market_id: int,
    profile: str = DEFAULT_PROFILE,
) -> ValuationDetailOut:
    if profile not in PROFILES:
        raise HTTPException(status_code=422, detail={"message": f"未知风险偏好：{profile}"})
    market = session.scalar(
        select(ValuationMarket)
        .where(ValuationMarket.id == valuation_market_id)
        .options(
            selectinload(ValuationMarket.listing),
            selectinload(ValuationMarket.report).selectinload(ValuationReport.instrument),
            selectinload(ValuationMarket.report)
            .selectinload(ValuationReport.markets)
            .selectinload(ValuationMarket.listing),
        )
    )
    if market is None or market.report is None:
        raise HTTPException(status_code=404, detail={"message": "估值记录不存在"})

    entry = session.scalar(
        select(RankingEntry)
        .join(RankingRun, RankingRun.id == RankingEntry.run_id)
        .where(
            RankingEntry.valuation_market_id == valuation_market_id,
            RankingRun.profile == profile,
            RankingRun.status == "published",
        )
        .order_by(RankingRun.as_of.desc(), RankingRun.id.desc())
        .limit(1)
    )
    report = market.report
    instrument = report.instrument
    raw_market = _raw_market(report, market)
    context = context_from_card(
        report.raw_card,
        raw_market,
        report.analysis_date,
    )
    rebuilt = score_context(context)
    quote = session.scalar(
        select(QuoteObservation)
        .where(QuoteObservation.listing_id == market.listing_id)
        .order_by(QuoteObservation.observed_at.desc(), QuoteObservation.id.desc())
        .limit(1)
    )
    current_price = quote.price if quote else market.price
    current_margin = effective_margin(context, current_price)
    score = ScoreOut(
        margin=rebuilt.score_margin,
        base=rebuilt.score_base,
        risk=rebuilt.score_risk,
        stability=rebuilt.score_stability,
        total=rebuilt.scores[profile],
        band=rebuilt.band,
    )
    if entry is not None:
        score = ScoreOut(
            margin=entry.score_margin,
            base=entry.score_base,
            risk=entry.score_risk,
            stability=entry.score_stability,
            total=entry.score,
            band=entry.band,
        )

    same_company = [
        MarketSummaryOut(
            valuation_market_id=other.id,
            market=other.listing.market,
            code=other.listing.code,
            currency=other.listing.currency,
            price=other.price,
            fair_mid=other.fair_mid,
            safety_margin_pct=other.safety_margin_pct,
            verdict=other.verdict,
        )
        for other in report.markets
        if other.id != market.id
    ]
    conclusion = report.raw_card.get("conclusion") or {}
    return ValuationDetailOut(
        valuation_market_id=market.id,
        report_id=report.id,
        instrument_id=instrument.id,
        name=instrument.name,
        market=market.listing.market,
        code=market.listing.code,
        currency=market.listing.currency,
        asset_type=instrument.asset_type,
        path=instrument.path,
        industry=instrument.industry,
        analysis_date=report.analysis_date,
        generated_at=report.generated_at,
        price_date=quote.quote_date if quote else market.price_date,
        stale_days=stale_days(report.analysis_date),
        quality=QualityOut(
            rating=instrument.quality_rating,
            label=instrument.quality_label,
            score=instrument.quality_score,
            moat=instrument.moat,
            gate_pass=instrument.gate_pass,
            gate_reason=instrument.gate_reason,
        ),
        cycle=CycleOut(stage=instrument.cycle_stage, position=instrument.cycle_position),
        conclusion={
            "verdict": str(conclusion.get("verdict") or ""),
            "thesis": str(conclusion.get("thesis") or ""),
            "confidence": str(conclusion.get("confidence") or ""),
        },
        price=current_price,
        baseline_price=market.price,
        current_price=current_price,
        fair_low=market.fair_low,
        fair_mid=market.fair_mid,
        fair_high=market.fair_high,
        safety_margin_pct=market.safety_margin_pct,
        effective_safety_margin_pct=(
            current_margin
        ),
        valuation={
            "pe": market.pe,
            "pb": market.pb,
            "dividend_yield_after_tax": market.dividend_yield_after_tax,
            "percentile": market.percentile,
        },
        gauges=market.gauges,
        expected_return=market.expected_return,
        downside=market.downside,
        position=market.position,
        verdict=market.verdict,
        score=score,
        risks=report.risks,
        missing=report.missing,
        notes=report.notes,
        risk_flags=entry.risk_flags if entry else rebuilt.risk_flags,
        excluded_reasons=entry.excluded_reasons if entry else rebuilt.excluded_reasons,
        same_company=same_company,
    )


def list_instruments(session: Session) -> InstrumentListOut:
    instruments = session.scalars(select(Instrument).order_by(Instrument.name)).all()
    items: list[InstrumentOut] = []
    for instrument in instruments:
        reports = session.scalars(
            select(ValuationReport)
            .where(ValuationReport.instrument_id == instrument.id)
            .order_by(ValuationReport.analysis_date.desc())
            .limit(1)
        ).all()
        markets = session.scalars(
            select(Listing.market)
            .where(Listing.instrument_id == instrument.id)
            .order_by(Listing.market)
        ).all()
        items.append(
            InstrumentOut(
                id=instrument.id,
                name=instrument.name,
                asset_type=instrument.asset_type,
                path=instrument.path,
                industry=instrument.industry,
                verdict=instrument.verdict,
                enabled=instrument.enabled,
                markets=list(markets),
                latest_analysis_date=reports[0].analysis_date if reports else None,
            )
        )
    return InstrumentListOut(items=items)


def _item_from_entry(
    entry: RankingEntry,
    stale_after: int,
    quote: QuoteObservation | None,
) -> RankingItemOut:
    market = entry.valuation_market
    report = market.report
    instrument = report.instrument
    age = stale_days(report.analysis_date)
    flags = list(entry.risk_flags)
    if age > stale_after and "估值数据偏旧" not in flags:
        flags.append("估值数据偏旧")
    return RankingItemOut(
        valuation_market_id=market.id,
        report_id=report.id,
        instrument_id=instrument.id,
        name=instrument.name,
        market=market.listing.market,
        code=market.listing.code,
        currency=market.listing.currency,
        industry=instrument.industry,
        path=instrument.path,
        analysis_date=report.analysis_date,
        stale_days=age,
        price=quote.price if quote else (entry.current_price or market.price),
        price_date=quote.quote_date if quote else market.price_date,
        fair_low=market.fair_low,
        fair_mid=market.fair_mid,
        fair_high=market.fair_high,
        safety_margin_pct=entry.effective_safety_margin_pct,
        expected_return=market.expected_return,
        max_drawdown_pct=entry.max_drawdown_pct,
        verdict=market.verdict,
        thesis=str((report.raw_card.get("conclusion") or {}).get("thesis") or ""),
        confidence=instrument.confidence,
        rank=entry.rank,
        score=ScoreOut(
            margin=entry.score_margin,
            base=entry.score_base,
            risk=entry.score_risk,
            stability=entry.score_stability,
            total=entry.score,
            band=entry.band,
        ),
        base_income=entry.base_income,
        risk_adjusted_ratio=entry.risk_adjusted_ratio,
        value_reliance=entry.value_reliance,
        risk_flags=flags,
        excluded_reasons=entry.excluded_reasons,
        is_etf=instrument.asset_type == "etf",
    )


def _raw_market(report: ValuationReport, market: ValuationMarket) -> dict[str, Any]:
    raw_markets = report.raw_card.get("markets") or []
    for item in raw_markets:
        if (
            str(item.get("market")) == market.listing.market
            and str(item.get("code")) == market.listing.code
        ):
            return dict(item)
    for item in raw_markets:
        if str(item.get("market")) == market.listing.market:
            return dict(item)
    return {
        "market": market.listing.market,
        "code": market.listing.code,
        "currency": market.listing.currency,
        "price": market.price,
        "fair_low": market.fair_low,
        "fair_mid": market.fair_mid,
        "fair_high": market.fair_high,
        "safety_margin_pct": market.safety_margin_pct,
        "expected_return": market.expected_return,
        "downside": market.downside,
        "gauges": market.gauges,
        "verdict": market.verdict,
    }


def _stale_after_days(session: Session) -> int:
    setting = session.scalar(select(ScheduleSetting).limit(1))
    return setting.stale_after_days if setting else 7
