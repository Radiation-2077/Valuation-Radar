from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import (
    Instrument,
    Listing,
    ScheduleSetting,
    ValuationMarket,
    ValuationReport,
)
from app.services.ranking import RankingService


class CardValidationError(ValueError):
    """Raised when a legacy valuation card does not satisfy the import contract."""


@dataclass(frozen=True)
class ImportSummary:
    files: int
    imported_reports: int
    skipped_reports: int
    instruments: int
    listings: int
    ranking_runs: int


def import_legacy_cards(
    session: Session,
    data_dir: Path | None = None,
    settings: Settings | None = None,
) -> ImportSummary:
    resolved_settings = settings or get_settings()
    source_data = (data_dir or resolved_settings.legacy_data_dir).resolve()
    if not source_data.is_dir():
        raise FileNotFoundError(f"数据卡目录不存在：{source_data}")

    cards: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(source_data.glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        validate_card(card, path)
        cards.append((path, card))
    cards.sort(
        key=lambda item: (
            item[1]["name"],
            item[1]["analysis_date"],
            item[1].get("generated_at") or "",
        )
    )

    imported = 0
    skipped = 0
    for _, card in cards:
        if _import_card(
            session,
            card,
            source="legacy",
            status="published",
        ):
            imported += 1
        else:
            skipped += 1

    if session.scalar(select(ScheduleSetting).limit(1)) is None:
        session.add(ScheduleSetting())

    session.flush()
    ranking_runs = RankingService().rebuild(session)
    session.commit()

    instrument_count = session.scalar(select(func.count()).select_from(Instrument)) or 0
    listing_count = session.scalar(select(func.count()).select_from(Listing)) or 0
    return ImportSummary(
        files=len(cards),
        imported_reports=imported,
        skipped_reports=skipped,
        instruments=instrument_count,
        listings=listing_count,
        ranking_runs=ranking_runs,
    )


def validate_card(card: dict[str, Any], source_path: Path | None = None) -> None:
    label = str(source_path or card.get("name") or "unknown")
    required = (
        "schema_version",
        "analysis_date",
        "name",
        "asset_type",
        "path",
        "quality",
        "conclusion",
        "macro",
        "markets",
    )
    missing = [key for key in required if key not in card]
    if missing:
        raise CardValidationError(f"{label} 缺少字段：{', '.join(missing)}")
    if card["schema_version"] != "1.0":
        raise CardValidationError(f"{label} schema_version 不是 1.0")
    try:
        analysis_date = date.fromisoformat(str(card["analysis_date"]))
    except ValueError as exc:
        raise CardValidationError(f"{label} analysis_date 非 ISO 日期") from exc
    if not isinstance(card.get("markets"), list) or not card["markets"]:
        raise CardValidationError(f"{label} markets 必须是非空数组")

    seen_markets: set[tuple[str, str]] = set()
    for market in card["markets"]:
        market_key = (str(market.get("market") or ""), str(market.get("code") or ""))
        if market_key in seen_markets:
            raise CardValidationError(f"{label} 存在重复市场：{market_key}")
        seen_markets.add(market_key)
        for key in ("price", "fair_low", "fair_mid", "fair_high", "expected_return"):
            if market.get(key) is None:
                raise CardValidationError(f"{label} {market_key[0]} 缺少 {key}")
        low = float(market["fair_low"])
        mid = float(market["fair_mid"])
        high = float(market["fair_high"])
        if not low <= mid <= high or mid <= 0:
            raise CardValidationError(f"{label} {market_key[0]} 合理区间顺序错误")
        drawdown = (market.get("downside") or {}).get("max_drawdown_pct")
        if isinstance(drawdown, (int, float)) and drawdown > 0:
            raise CardValidationError(f"{label} {market_key[0]} 最大回撤必须为负数")
        safety_margin = market.get("safety_margin_pct")
        if isinstance(safety_margin, (int, float)):
            expected = (mid - float(market["price"])) / mid * 100
            if abs(expected - float(safety_margin)) > 0.25:
                raise CardValidationError(f"{label} {market_key[0]} 安全边际与现价/中枢不一致")
    if analysis_date > date.today():
        raise CardValidationError(f"{label} analysis_date 晚于当前日期")


def _import_card(
    session: Session,
    card: dict[str, Any],
    source: str,
    status: str,
    apply_metadata: bool = True,
) -> bool:
    card_bytes = json.dumps(card, ensure_ascii=False, sort_keys=True).encode("utf-8")
    card_hash = hashlib.sha256(card_bytes).hexdigest()
    analysis_date = date.fromisoformat(str(card["analysis_date"]))
    conclusion = card["conclusion"]

    instrument = session.scalar(select(Instrument).where(Instrument.name == card["name"]))
    if instrument is None:
        instrument = Instrument(name=str(card["name"]))
        session.add(instrument)
    if apply_metadata:
        apply_instrument_metadata(instrument, card)
    session.flush()

    existing = session.scalar(
        select(ValuationReport).where(
            ValuationReport.instrument_id == instrument.id,
            ValuationReport.analysis_date == analysis_date,
            ValuationReport.card_sha256 == card_hash,
        )
    )
    if existing is not None:
        return False

    revision = (
        session.scalar(
            select(func.max(ValuationReport.revision)).where(
                ValuationReport.instrument_id == instrument.id,
                ValuationReport.analysis_date == analysis_date,
            )
        )
        or 0
    ) + 1
    generated_at = _parse_datetime(card.get("generated_at"))
    report = ValuationReport(
        instrument_id=instrument.id,
        analysis_date=analysis_date,
        generated_at=generated_at,
        revision=revision,
        schema_version=str(card["schema_version"]),
        source=source,
        macro=dict(card.get("macro") or {}),
        risks=[str(item) for item in card.get("risks") or []],
        missing=[str(item) for item in card.get("missing") or []],
        notes=str(card.get("notes") or ""),
        raw_card=card,
        card_sha256=card_hash,
        status=status,
    )
    session.add(report)
    session.flush()

    codes = card.get("codes") or {}
    for market in card["markets"]:
        market_code = str(market.get("code") or codes.get(str(market.get("market"))) or "")
        if not market_code:
            raise CardValidationError(f"{card['name']} 市场缺少证券代码")
        listing = session.scalar(
            select(Listing).where(
                Listing.market == str(market.get("market") or ""),
                Listing.code == market_code,
            )
        )
        if listing is None:
            listing = Listing(
                instrument_id=instrument.id,
                market=str(market.get("market") or ""),
                code=market_code,
                currency=str(market.get("currency") or "CNY"),
            )
            session.add(listing)
            session.flush()
        elif listing.instrument_id != instrument.id:
            raise CardValidationError(f"证券代码 {market_code} 已属于其他标的")

        valuation = market.get("valuation") or {}
        session.add(
            ValuationMarket(
                report_id=report.id,
                listing_id=listing.id,
                price=float(market["price"]),
                price_date=_parse_date(market.get("price_date"), analysis_date),
                fair_low=float(market["fair_low"]),
                fair_mid=float(market["fair_mid"]),
                fair_high=float(market["fair_high"]),
                safety_margin_pct=_optional_float(market.get("safety_margin_pct")),
                pe=_optional_float(valuation.get("pe")),
                pb=_optional_float(valuation.get("pb")),
                dividend_yield_after_tax=_optional_float(valuation.get("dividend_yield_after_tax")),
                percentile=_optional_float(valuation.get("percentile")),
                gauges=dict(market.get("gauges") or {}),
                expected_return=dict(market["expected_return"]),
                downside=dict(market.get("downside") or {}),
                position=dict(market.get("position") or {}),
                verdict=str(market.get("verdict") or conclusion.get("verdict") or ""),
            )
        )
    return True


def import_candidate_card(
    session: Session,
    card_path: Path,
) -> ValuationReport:
    card = json.loads(card_path.read_text(encoding="utf-8"))
    validate_card(card, card_path)
    instrument = session.scalar(select(Instrument).where(Instrument.name == card["name"]))
    if instrument is None:
        raise CardValidationError(f"候选估值对应的标的不存在：{card['name']}")
    imported = _import_card(
        session,
        card,
        source="codex",
        status="needs_review",
        apply_metadata=False,
    )
    card_hash = hashlib.sha256(
        json.dumps(card, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    report = session.scalar(
        select(ValuationReport).where(
            ValuationReport.instrument_id == instrument.id,
            ValuationReport.card_sha256 == card_hash,
        )
    )
    if report is None:
        raise RuntimeError("候选估值导入后未能找到版本记录" if not imported else "候选估值导入失败")
    return report


def apply_instrument_metadata(instrument: Instrument, card: dict[str, Any]) -> None:
    quality = card["quality"]
    conclusion = card["conclusion"]
    instrument.asset_type = str(card["asset_type"])
    instrument.path = str(card["path"])
    instrument.industry = str(card.get("industry") or "")
    instrument.cycle_stage = str(card.get("cycle_stage") or "")
    instrument.cycle_position = _optional_float(card.get("cycle_position"))
    instrument.quality_rating = int(quality.get("rating") or 0)
    instrument.quality_label = str(quality.get("label") or "")
    instrument.quality_score = float(quality.get("score") or 0)
    instrument.moat = str(quality.get("moat") or "")
    instrument.gate_pass = bool(quality.get("gate_pass", False))
    instrument.gate_reason = str(quality.get("gate_reason") or "")
    instrument.verdict = str(conclusion.get("verdict") or "")
    instrument.thesis = str(conclusion.get("thesis") or "")
    instrument.confidence = str(conclusion.get("confidence") or "中")


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _parse_date(value: object, default: date) -> date:
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return default


def _optional_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
