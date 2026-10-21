from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.scoring import (
    DEFAULT_PROFILE,
    PROFILES,
    context_from_card,
    rank_entries,
    score_context,
)
from app.models import (
    RankingEntry,
    RankingRun,
    ValuationMarket,
    ValuationReport,
)


class RankingService:
    def rebuild(self, session: Any, as_of: datetime | None = None) -> int:
        run_time = as_of or datetime.now(UTC).replace(tzinfo=None)
        contexts = self._latest_contexts(session)
        if not contexts:
            return 0

        created = 0
        for profile in PROFILES.values():
            scored = rank_entries(
                [score_context(context) for context, _ in contexts],
                profile.code,
            )
            reference_by_key = {
                (context.name, context.market, context.code): valuation_market_id
                for context, valuation_market_id in contexts
            }
            config_hash = hashlib.sha256(
                f"{profile.code}:{profile.margin}:{profile.base}:{profile.risk}:"
                f"{profile.stability}".encode()
            ).hexdigest()
            run = RankingRun(
                as_of=run_time,
                profile=profile.code,
                algorithm_version="1.0",
                config_hash=config_hash,
                status="published",
            )
            session.add(run)
            session.flush()

            rank = 0
            for entry in scored:
                valuation_market_id = reference_by_key[
                    (entry.context.name, entry.context.market, entry.context.code)
                ]
                is_main_board = not entry.excluded_reasons and not entry.context.is_etf
                if is_main_board:
                    rank += 1
                session.add(
                    RankingEntry(
                        run_id=run.id,
                        valuation_market_id=valuation_market_id,
                        rank=rank if is_main_board else None,
                        band=entry.band,
                        score=entry.scores[profile.code],
                        score_margin=entry.score_margin,
                        score_base=entry.score_base,
                        score_risk=entry.score_risk,
                        score_stability=entry.score_stability,
                        effective_safety_margin_pct=entry.effective_safety_margin_pct,
                        current_price=entry.context.price,
                        base_income=entry.base_income,
                        expected_total=entry.expected_total,
                        max_drawdown_pct=entry.context.max_drawdown_pct,
                        risk_adjusted_ratio=entry.risk_adjusted_ratio,
                        value_reliance=entry.value_reliance,
                        excluded_reasons=entry.excluded_reasons,
                        risk_flags=entry.risk_flags,
                    )
                )
            created += 1
        session.flush()
        return created

    def _latest_contexts(self, session: Any) -> list[tuple[Any, int]]:
        reports = (
            session.scalars(
                select(ValuationReport)
                .where(ValuationReport.status == "published")
                .options(
                    selectinload(ValuationReport.instrument),
                    selectinload(ValuationReport.markets).selectinload(ValuationMarket.listing),
                )
            )
            .unique()
            .all()
        )
        latest: dict[int, ValuationReport] = {}
        for report in reports:
            current = latest.get(report.instrument_id)
            report_key = (
                report.analysis_date,
                report.revision,
                report.generated_at or datetime.min,
            )
            current_key = (
                (current.analysis_date, current.revision, current.generated_at or datetime.min)
                if current
                else None
            )
            if current_key is None or report_key > current_key:
                latest[report.instrument_id] = report

        output: list[tuple[Any, int]] = []
        for report in latest.values():
            raw_markets = report.raw_card.get("markets") or []
            for market in report.markets:
                raw_market = _find_raw_market(
                    raw_markets,
                    market.listing.market,
                    market.listing.code,
                )
                if raw_market is None:
                    continue
                context = context_from_card(report.raw_card, raw_market, report.analysis_date)
                output.append((context, market.id))
        return output


def latest_run(session: Any, profile: str = DEFAULT_PROFILE) -> RankingRun | None:
    if profile not in PROFILES:
        raise ValueError(f"未知风险偏好：{profile}")
    return session.scalar(
        select(RankingRun)
        .where(RankingRun.profile == profile, RankingRun.status == "published")
        .order_by(RankingRun.as_of.desc(), RankingRun.id.desc())
        .limit(1)
    )


def _find_raw_market(
    markets: list[dict[str, Any]],
    market_name: str,
    code: str,
) -> dict[str, Any] | None:
    for market in markets:
        if str(market.get("market")) == market_name and str(market.get("code")) == code:
            return market
    for market in markets:
        if str(market.get("market")) == market_name:
            return market
    return None


def stale_days(analysis_date: date, as_of: date | None = None) -> int:
    return max(0, ((as_of or date.today()) - analysis_date).days)
