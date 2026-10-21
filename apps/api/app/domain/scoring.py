from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

ALGORITHM_VERSION = "1.0"

ANCHOR_MARGIN = [
    (-30.0, 0.0),
    (-15.0, 10.0),
    (0.0, 42.0),
    (10.0, 60.0),
    (20.0, 76.0),
    (30.0, 87.0),
    (40.0, 95.0),
    (60.0, 100.0),
]
ANCHOR_EXCESS = [
    (-3.0, 8.0),
    (-1.0, 22.0),
    (0.0, 35.0),
    (2.0, 50.0),
    (4.0, 62.0),
    (6.0, 72.0),
    (8.0, 82.0),
    (12.0, 93.0),
    (18.0, 100.0),
]
ANCHOR_DRAWDOWN = [
    (10.0, 97.0),
    (16.0, 90.0),
    (22.0, 80.0),
    (26.0, 72.0),
    (31.0, 62.0),
    (36.0, 52.0),
    (42.0, 42.0),
    (50.0, 30.0),
    (60.0, 18.0),
]


@dataclass(frozen=True)
class Profile:
    code: str
    label: str
    margin: float
    base: float
    risk: float
    stability: float
    description: str


PROFILES = {
    "conservative": Profile("conservative", "稳健保守", 0.25, 0.15, 0.30, 0.30, "风险与确定性优先"),
    "balanced": Profile("balanced", "均衡", 0.30, 0.25, 0.20, 0.25, "默认基准"),
    "aggressive": Profile("aggressive", "进取", 0.25, 0.40, 0.15, 0.20, "以预期收益为主"),
}
DEFAULT_PROFILE = "balanced"


@dataclass(frozen=True)
class SecurityContext:
    name: str
    market: str
    code: str
    currency: str
    asset_type: str
    path: str
    industry: str
    analysis_date: date
    rating: float
    quality_score: float
    gate_pass: bool
    gate_reason: str
    cycle_position: float | None
    price: float
    fair_mid: float
    safety_margin_pct: float | None
    expected_return: dict[str, Any]
    max_drawdown_pct: float | None
    certainty: float | None
    verdict: str
    thesis: str
    confidence: str
    risks: list[str]
    missing: list[str]
    rf_cny: float | None
    rf_usd: float | None
    is_etf: bool = False


@dataclass(frozen=True)
class ScoredEntry:
    context: SecurityContext
    effective_safety_margin_pct: float | None
    score_margin: float | None
    score_base: float | None
    score_risk: float | None
    score_stability: float
    band: str
    scores: dict[str, float | None]
    base_income: float
    expected_total: float | None
    risk_adjusted_ratio: float | None
    value_reliance: float
    excluded_reasons: list[str]
    risk_flags: list[str]


def lerp_anchor(value: float, anchors: list[tuple[float, float]]) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:], strict=False):
        if x0 <= value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return anchors[-1][1]


def band_of(score: float) -> str:
    if score >= 75:
        return "S"
    if score >= 65:
        return "A"
    if score >= 55:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def risk_free_rate(context: SecurityContext) -> float:
    if context.currency.upper() == "CNY":
        return context.rf_cny if context.rf_cny is not None else 1.7
    return context.rf_usd if context.rf_usd is not None else (context.rf_cny or 4.5)


def effective_margin(context: SecurityContext, current_price: float | None = None) -> float | None:
    if not context.fair_mid:
        return None
    price = current_price if current_price is not None else context.price
    return (context.fair_mid - price) / context.fair_mid * 100


def score_context(context: SecurityContext, current_price: float | None = None) -> ScoredEntry:
    expected = context.expected_return
    dividend = _number(expected.get("dividend"), 0.0) or 0.0
    growth = _number(expected.get("growth"), 0.0) or 0.0
    fx = _number(expected.get("fx"), 0.0) or 0.0
    valuation = _number(expected.get("valuation"), 0.0) or 0.0
    total = _number(expected.get("total"))
    drawdown = context.max_drawdown_pct
    margin = (
        context.safety_margin_pct
        if current_price is None and context.safety_margin_pct is not None
        else effective_margin(context, current_price)
    )
    base_income = dividend + growth + fx
    rate = risk_free_rate(context)

    score_margin = lerp_anchor(margin, ANCHOR_MARGIN) if margin is not None else None
    score_base = lerp_anchor(base_income - rate, ANCHOR_EXCESS)
    score_risk = lerp_anchor(abs(drawdown), ANCHOR_DRAWDOWN) if drawdown is not None else None
    if score_risk is not None and context.cycle_position is not None:
        adjustment = -(context.cycle_position - 50) / 50 * 8
        score_risk = _clamp(score_risk + adjustment, 0, 100)

    certainty = context.certainty if context.certainty is not None else context.quality_score
    score_stability = 0.55 * context.quality_score + 0.45 * certainty
    if context.path == "cyclical":
        score_stability -= 6
    if context.asset_type == "etf" or context.is_etf:
        score_stability -= 4
    if context.rating <= 1:
        score_stability *= 0.5
    if context.confidence == "低":
        score_stability -= 5
    score_stability = _clamp(score_stability, 0, 100)

    excluded: list[str] = []
    if not context.gate_pass:
        excluded.append(context.gate_reason or "未通过质地门槛")
    if context.rating < 2:
        excluded.append(f"质地 {context.rating:g}★ 不达标")
    if margin is None:
        excluded.append("安全边际缺失")
    if total is None:
        excluded.append("预期年化缺失")
    if drawdown is None:
        excluded.append("最大回撤缺失")

    scores: dict[str, float | None] = {}
    for profile in PROFILES.values():
        if score_margin is None or score_risk is None:
            scores[profile.code] = None
        else:
            scores[profile.code] = (
                profile.margin * score_margin
                + profile.base * score_base
                + profile.risk * score_risk
                + profile.stability * score_stability
            )

    risk_adjusted_ratio = (
        (total - rate) / abs(drawdown)
        if total is not None and drawdown is not None and drawdown != 0
        else None
    )
    value_reliance = abs(valuation) / abs(total) if total is not None and abs(total) > 0.01 else 0.0

    risk_flags: list[str] = []
    if value_reliance > 0.4:
        risk_flags.append("依赖估值回归")
    if context.cycle_position is not None and context.cycle_position >= 80:
        risk_flags.append("周期位置偏高")
    if context.missing:
        risk_flags.append("存在缺失字段")
    if not risk_flags:
        risk_flags.append("常规跟踪")

    return ScoredEntry(
        context=context,
        effective_safety_margin_pct=margin,
        score_margin=score_margin,
        score_base=score_base,
        score_risk=score_risk,
        score_stability=score_stability,
        band="D",
        scores=scores,
        base_income=base_income,
        expected_total=total,
        risk_adjusted_ratio=risk_adjusted_ratio,
        value_reliance=value_reliance,
        excluded_reasons=excluded,
        risk_flags=risk_flags,
    )


def rank_entries(entries: list[ScoredEntry], profile_code: str) -> list[ScoredEntry]:
    ranked: list[ScoredEntry] = []
    for entry in entries:
        score = entry.scores[profile_code]
        band = band_of(score) if score is not None else "D"
        ranked.append(
            ScoredEntry(
                context=entry.context,
                effective_safety_margin_pct=entry.effective_safety_margin_pct,
                score_margin=entry.score_margin,
                score_base=entry.score_base,
                score_risk=entry.score_risk,
                score_stability=entry.score_stability,
                band=band,
                scores=entry.scores,
                base_income=entry.base_income,
                expected_total=entry.expected_total,
                risk_adjusted_ratio=entry.risk_adjusted_ratio,
                value_reliance=entry.value_reliance,
                excluded_reasons=entry.excluded_reasons,
                risk_flags=entry.risk_flags,
            )
        )
    return sorted(
        ranked,
        key=lambda item: (
            bool(item.excluded_reasons),
            item.context.is_etf or item.context.asset_type == "etf",
            -(item.scores[profile_code] or -1),
            item.context.name,
            item.context.market,
        ),
    )


def context_from_card(
    card: dict[str, Any],
    market: dict[str, Any],
    analysis_date: date,
) -> SecurityContext:
    quality = card.get("quality") or {}
    conclusion = card.get("conclusion") or {}
    macro = card.get("macro") or {}
    gauges = market.get("gauges") or {}
    return SecurityContext(
        name=str(card["name"]),
        market=str(market.get("market") or "—"),
        code=str(market.get("code") or ""),
        currency=str(market.get("currency") or "CNY"),
        asset_type=str(card.get("asset_type") or "stock"),
        path=str(card.get("path") or "stable"),
        industry=str(card.get("industry") or ""),
        analysis_date=analysis_date,
        rating=_number(quality.get("rating"), 0.0) or 0.0,
        quality_score=_number(quality.get("score"), 60.0) or 60.0,
        gate_pass=bool(quality.get("gate_pass", True)),
        gate_reason=str(quality.get("gate_reason") or ""),
        cycle_position=_number(card.get("cycle_position")),
        price=_number(market.get("price"), 0.0) or 0.0,
        fair_mid=_number(market.get("fair_mid"), 0.0) or 0.0,
        safety_margin_pct=_number(market.get("safety_margin_pct")),
        expected_return=dict(market.get("expected_return") or {}),
        max_drawdown_pct=_number((market.get("downside") or {}).get("max_drawdown_pct")),
        certainty=_number(gauges.get("certainty")),
        verdict=str(market.get("verdict") or conclusion.get("verdict") or ""),
        thesis=str(conclusion.get("thesis") or ""),
        confidence=str(conclusion.get("confidence") or "中"),
        risks=[str(item) for item in card.get("risks") or []],
        missing=[str(item) for item in card.get("missing") or []],
        rf_cny=_number(macro.get("rf_cny")),
        rf_usd=_number(macro.get("rf_usd")),
        is_etf=str(card.get("asset_type") or "") == "etf",
    )


def _number(value: object, default: float | None = None) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
