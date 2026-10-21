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
from app.services.report_parser import parse_report_detail

SUPPORTED_SCHEMA_VERSIONS = {"1.0", "1.1"}
PRESENTATION_MARKETS = {"common", "A", "H", "US", "CN"}
QUALITY_LABELS = (
    "利润现金含量",
    "资产负债表",
    "ROE 水平",
    "护城河强度",
    "生存能力",
)


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
    source_reports = resolved_settings.legacy_reports_dir.resolve()
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
        html_path = source_reports / f"{card['name']}_估值分析_{card['analysis_date']}.html"
        detail_json = _detail_json(card, html_path)
        if _import_card(
            session,
            card,
            detail_json,
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
    schema_version = str(card["schema_version"])
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise CardValidationError(
            f"{label} schema_version 非法：{schema_version}（支持 1.0 / 1.1）"
        )
    if schema_version == "1.1":
        canonicalize_presentation_quality(card)
        _validate_presentation(card, label)
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


def _detail_json(card: dict[str, Any], html_path: Path) -> dict[str, Any]:
    if card["schema_version"] == "1.1":
        return dict(card["presentation"])
    if html_path.is_file():
        return parse_report_detail(html_path)
    return {}


def _import_card(
    session: Session,
    card: dict[str, Any],
    detail_json: dict[str, Any],
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
        if detail_json:
            existing.detail_json = detail_json
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
        detail_json=detail_json,
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
    if card["schema_version"] != "1.1":
        raise CardValidationError("新候选估值必须使用 schema 1.1")
    instrument = session.scalar(select(Instrument).where(Instrument.name == card["name"]))
    if instrument is None:
        raise CardValidationError(f"候选估值对应的标的不存在：{card['name']}")
    imported = _import_card(
        session,
        card,
        dict(card["presentation"]),
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


def _validate_presentation(card: dict[str, Any], label: str) -> None:
    presentation = card.get("presentation")
    if not isinstance(presentation, dict):
        raise CardValidationError(f"{label} schema 1.1 缺少 presentation 对象")
    sections = presentation.get("sections")
    if not isinstance(sections, list) or not sections:
        raise CardValidationError(f"{label} presentation.sections 必须是非空数组")

    section_ids: set[str] = set()
    quality_grids: list[dict[str, Any]] = []
    for section_index, section in enumerate(sections):
        section_tag = f"presentation.sections[{section_index}]"
        if not isinstance(section, dict):
            raise CardValidationError(f"{label} {section_tag} 必须是对象")
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id:
            raise CardValidationError(f"{label} {section_tag}.id 缺失")
        if section_id in section_ids:
            raise CardValidationError(f"{label} {section_tag}.id 重复：{section_id}")
        section_ids.add(section_id)
        if not isinstance(section.get("title"), str) or not section["title"]:
            raise CardValidationError(f"{label} {section_tag}.title 缺失")
        if section.get("market") not in PRESENTATION_MARKETS:
            raise CardValidationError(f"{label} {section_tag}.market 非法")
        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise CardValidationError(f"{label} {section_tag}.blocks 必须是非空数组")
        for block_index, block in enumerate(blocks):
            block_tag = f"{section_tag}.blocks[{block_index}]"
            if not isinstance(block, dict):
                raise CardValidationError(f"{label} {block_tag} 必须是对象")
            if not isinstance(block.get("type"), str) or not block["type"]:
                raise CardValidationError(f"{label} {block_tag}.type 缺失")
            if block["type"] == "grid" and _quality_grid_parts(block) is not None:
                quality_grids.append(block)

    if len(quality_grids) != 1:
        raise CardValidationError(
            f"{label} schema 1.1 必须且只能包含一个质量 grid（scores + table）"
        )
    _validate_quality_grid(quality_grids[0], label)
    _validate_ah_sections(card, sections, label)


def _validate_quality_grid(block: dict[str, Any], label: str) -> None:
    parts = _quality_grid_parts(block)
    if parts is None:
        raise CardValidationError(f"{label} 质量 grid 必须包含 scores 与 table")
    scores, table = parts
    items = scores.get("items")
    if not isinstance(items, list) or len(items) != 5:
        raise CardValidationError(f"{label} 质量 grid.scores.items 必须恰好 5 项")
    labels = [str(item.get("label") or "") for item in items if isinstance(item, dict)]
    if labels != list(QUALITY_LABELS):
        raise CardValidationError(f"{label} 质量 grid 五个维度顺序或名称不正确")
    for item in items:
        if not isinstance(item, dict):
            raise CardValidationError(f"{label} 质量 grid.scores 含非对象项")
        try:
            score = float(str(item.get("score")))
            width = float(str(item.get("width")))
        except (TypeError, ValueError) as exc:
            raise CardValidationError(f"{label} 质量 grid score/width 必须为数值") from exc
        if not 0 <= score <= 10 or not 0 <= width <= 100:
            raise CardValidationError(f"{label} 质量 grid score/width 越界")
    rows = table.get("rows")
    if not isinstance(rows, list) or len(rows) != 5:
        raise CardValidationError(f"{label} 质量 grid.table.rows 必须恰好 5 行")
    if any(not isinstance(row, list) or len(row) != 3 for row in rows):
        raise CardValidationError(f"{label} 质量 grid.table 每行必须为 3 列")


def _quality_grid_parts(
    block: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    columns = block.get("columns")
    if not isinstance(columns, list):
        return None
    blocks = [
        item
        for column in columns
        if isinstance(column, list)
        for item in column
        if isinstance(item, dict)
    ]
    scores = next((item for item in blocks if item.get("type") == "scores"), None)
    table = next((item for item in blocks if item.get("type") == "table"), None)
    if scores is None or table is None:
        return None
    return scores, table


def canonicalize_presentation_quality(card: dict[str, Any]) -> None:
    presentation = card.get("presentation")
    if not isinstance(presentation, dict):
        return
    sections = presentation.get("sections")
    if not isinstance(sections, list):
        return
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("blocks"), list):
            continue
        section["blocks"] = [
            _quality_scorecard_to_grid(block)
            if isinstance(block, dict) and block.get("type") == "quality_scorecard"
            else block
            for block in section["blocks"]
        ]


def _quality_scorecard_to_grid(block: dict[str, Any]) -> dict[str, Any]:
    dimensions = block.get("dimensions")
    if not isinstance(dimensions, list):
        return block
    scale_max = block.get("scale_max", 10)
    try:
        maximum = float(str(scale_max))
    except (TypeError, ValueError):
        maximum = 10.0
    score_items = []
    rows = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        try:
            score = float(str(dimension.get("score")))
        except (TypeError, ValueError):
            score = 0.0
        score_items.append(
            {
                "label": str(dimension.get("label") or ""),
                "score": f"{score:.1f}",
                "width": round(score / maximum * 100, 1) if maximum > 0 else 0,
                "tone": "negative" if score < maximum / 2 else "positive",
            }
        )
        rows.append(
            [
                str(dimension.get("indicator") or ""),
                str(dimension.get("value") or ""),
                str(dimension.get("assessment") or ""),
            ]
        )
    return {
        "type": "grid",
        "columns": [
            [
                {"type": "heading", "level": 3, "text": "质量分项（0–10）"},
                {"type": "scores", "items": score_items},
            ],
            [
                {"type": "heading", "level": 3, "text": "关键指标"},
                {
                    "type": "table",
                    "headers": ["维度", "结果", "评价"],
                    "rows": rows,
                },
            ],
        ],
    }


def _validate_ah_sections(
    card: dict[str, Any],
    sections: list[Any],
    label: str,
) -> None:
    market_names = {
        str(market.get("market"))
        for market in card.get("markets") or []
        if isinstance(market, dict)
    }
    if not {"A", "H"}.issubset(market_names):
        return
    expected_markets = {
        "dashboard-A": "A",
        "dashboard-H": "H",
        "quality": "common",
        "cycle": "common",
        "cross_market": "common",
        "valuation-A": "A",
        "valuation-H": "H",
        "position-A": "A",
        "position-H": "H",
        "expected_return-A": "A",
        "expected_return-H": "H",
        "risks-A": "A",
        "risks-H": "H",
        "conclusion-A": "A",
        "conclusion-H": "H",
        "sources": "common",
        "disclaimer": "common",
    }
    sections_by_id = {
        str(section.get("id")): section
        for section in sections
        if isinstance(section, dict)
    }
    missing = sorted(set(expected_markets) - set(sections_by_id))
    if missing:
        raise CardValidationError(
            f"{label} A+H presentation 缺少 section：{', '.join(missing)}"
        )
    for section_id, expected_market in expected_markets.items():
        section = sections_by_id[section_id]
        if section.get("market") != expected_market:
            raise CardValidationError(
                f"{label} {section_id}.market 必须为 {expected_market}"
            )
        if expected_market != "common":
            for block in section.get("blocks") or []:
                block_market = block.get("market") if isinstance(block, dict) else None
                if block_market not in {None, expected_market}:
                    raise CardValidationError(
                        f"{label} {section_id} 混入 {block_market} 市场区块"
                    )
    forbidden_cross_market_blocks = {
        "valuation_scenarios",
        "range_position",
        "position_tiers",
        "return_stack",
    }
    cross_market = sections_by_id["cross_market"]
    for block in cross_market.get("blocks") or []:
        if isinstance(block, dict) and block.get("type") in forbidden_cross_market_blocks:
            raise CardValidationError(
                f"{label} cross_market 不得包含 {block['type']}，该章只比较溢价"
            )


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
