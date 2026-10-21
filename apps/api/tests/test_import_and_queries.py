from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.models import Instrument
from app.services.importer import (
    CardValidationError,
    import_candidate_card,
    import_legacy_cards,
    validate_card,
)
from app.services.queries import get_ranking, get_valuation_detail

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LEGACY_DATA_DIR = PROJECT_ROOT.parent / "data"


@pytest.mark.skipif(not LEGACY_DATA_DIR.is_dir(), reason="需要现有数据卡")
def test_imports_legacy_cards_and_serves_ranking(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(storage_root=tmp_path / "storage")

    with Session(engine) as session:
        first = import_legacy_cards(
            session,
            data_dir=LEGACY_DATA_DIR,
            settings=settings,
        )
        assert first.files == 21
        assert first.imported_reports == 21
        assert first.instruments == 19
        assert first.listings == 29
        assert first.ranking_runs == 3

        ranking = get_ranking(session, profile="balanced")
        assert ranking.counts["all"] == 29
        assert ranking.counts["main_board"] > 0
        assert len(ranking.top_three) == 3
        assert ranking.top_three[0].rank == 1

        detail = get_valuation_detail(
            session,
            ranking.top_three[0].valuation_market_id,
            profile="balanced",
        )
        assert detail.name == ranking.top_three[0].name
        assert detail.fair_low <= detail.fair_mid <= detail.fair_high
        assert detail.score.total is not None
        assert "hkd_cny" in detail.macro
        assert detail.report_detail["sections"]
        assert any(
            "标的质地" in section["title"]
            for section in detail.report_detail["sections"]
        )
        if detail.same_company:
            assert detail.same_company[0].fair_low <= detail.same_company[0].fair_mid
            assert detail.same_company[0].gauges
            assert detail.same_company[0].expected_return

        second = import_legacy_cards(
            session,
            data_dir=LEGACY_DATA_DIR,
            settings=settings,
        )
        assert second.skipped_reports == 21
        assert second.instruments == 19


@pytest.mark.skipif(not LEGACY_DATA_DIR.is_dir(), reason="需要现有数据卡")
def test_schema_1_1_candidate_persists_presentation(tmp_path: Path) -> None:
    source_card = json.loads(
        sorted(LEGACY_DATA_DIR.glob("*.json"))[0].read_text(encoding="utf-8")
    )
    presentation = _quality_presentation()
    source_card["schema_version"] = "1.1"
    source_card["presentation"] = presentation
    validate_card(source_card)

    engine = create_engine(f"sqlite:///{tmp_path / 'schema-1-1.db'}")
    Base.metadata.create_all(engine)
    card_path = tmp_path / f"{source_card['name']}_{source_card['analysis_date']}.json"
    card_path.write_text(
        json.dumps(source_card, ensure_ascii=False),
        encoding="utf-8",
    )

    with Session(engine) as session:
        session.add(Instrument(name=source_card["name"]))
        session.commit()

        report = import_candidate_card(session, card_path)
        assert report.schema_version == "1.1"
        assert report.detail_json == presentation

        detail = get_valuation_detail(session, report.markets[0].id)
        assert detail.report_detail["sections"][0]["blocks"][0]["type"] == "quality_scorecard"


@pytest.mark.skipif(not LEGACY_DATA_DIR.is_dir(), reason="需要现有数据卡")
def test_schema_1_1_rejects_missing_quality_scorecard() -> None:
    card = json.loads(
        sorted(LEGACY_DATA_DIR.glob("*.json"))[0].read_text(encoding="utf-8")
    )
    card["schema_version"] = "1.1"
    card["presentation"] = {
        "schema_version": "1.0",
        "sections": [
            {
                "id": "quality",
                "title": "标的质地",
                "market": "common",
                "blocks": [{"type": "paragraph", "text": "缺少质量评分卡"}],
            }
        ],
    }

    with pytest.raises(CardValidationError, match="quality_scorecard"):
        validate_card(card)


@pytest.mark.skipif(not LEGACY_DATA_DIR.is_dir(), reason="需要现有数据卡")
def test_schema_1_1_ah_requires_split_market_sections() -> None:
    card = json.loads(
        (LEGACY_DATA_DIR / "中国平安_2026-10-13.json").read_text(encoding="utf-8")
    )
    card["schema_version"] = "1.1"
    card["presentation"] = _quality_presentation()

    with pytest.raises(CardValidationError, match="dashboard-A"):
        validate_card(card)


def _quality_presentation() -> dict:
    dimensions = [
        {
            "key": "profit_cash_quality",
            "label": "利润现金含量",
            "score": 8.0,
            "indicator": "经营现金流 / 净利润",
            "value": "1.2 倍",
            "assessment": "真实",
        },
        {
            "key": "balance_sheet",
            "label": "资产负债表",
            "score": 8.0,
            "indicator": "有息负债率",
            "value": "20%",
            "assessment": "稳健",
        },
        {
            "key": "roe",
            "label": "ROE 水平",
            "score": 7.0,
            "indicator": "ROE（近 3 年均值）",
            "value": "12%",
            "assessment": "中上",
        },
        {
            "key": "moat",
            "label": "护城河强度",
            "score": 8.0,
            "indicator": "护城河",
            "value": "规模与成本",
            "assessment": "强",
        },
        {
            "key": "survival",
            "label": "生存能力",
            "score": 7.0,
            "indicator": "压力年份",
            "value": "保持盈利",
            "assessment": "通过",
        },
    ]
    return {
        "schema_version": "1.0",
        "sections": [
            {
                "id": "quality",
                "title": "标的质地",
                "market": "common",
                "blocks": [
                    {
                        "type": "quality_scorecard",
                        "scale_max": 10,
                        "dimensions": dimensions,
                    },
                    {
                        "type": "callout",
                        "tone": "info",
                        "title": "本章小结",
                        "body": "质量可接受。",
                        "summary": True,
                    },
                ],
            }
        ],
    }
