from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_engine_for_url
from app.models import (
    Instrument,
    Listing,
    RankingEntry,
    ValuationMarket,
    ValuationReport,
)
from app.services.importer import (
    CardValidationError,
    import_candidate_card,
    import_legacy_cards,
    validate_card,
)
from app.services.instruments import (
    archive_instrument,
    purge_instrument,
    restore_instrument,
)
from app.services.queries import get_ranking, get_valuation_detail
from app.services.ranking import latest_run

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_EXAMPLE = (
    PROJECT_ROOT
    / "schemas"
    / "value-investing"
    / "examples"
    / "card-v1.2.example.json"
)


def write_contract_card(directory: Path) -> Path:
    card = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{card['name']}_{card['analysis_date']}.json"
    path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return path


def test_imports_contract_card_and_serves_ranking(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(storage_root=tmp_path / "storage")
    data_dir = tmp_path / "cards"
    write_contract_card(data_dir)

    with Session(engine) as session:
        first = import_legacy_cards(
            session,
            data_dir=data_dir,
            settings=settings,
        )
        assert first.files == 1
        assert first.imported_reports == 1
        assert first.instruments == 1
        assert first.listings == 2
        assert first.ranking_runs == 3

        ranking = get_ranking(session, profile="balanced")
        assert ranking.counts["all"] == 2
        assert ranking.counts["main_board"] == 2
        assert len(ranking.top_three) == 2
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
            section["title"] == "标的质地"
            for section in detail.report_detail["sections"]
        )
        assert detail.same_company

        second = import_legacy_cards(
            session,
            data_dir=data_dir,
            settings=settings,
        )
        assert second.skipped_reports == 1
        assert second.instruments == 1

        archive_instrument(session, ranking.top_three[0].instrument_id)
        session.commit()
        archived_run = latest_run(session, profile="balanced")
        assert archived_run is not None
        archived_ranking = get_ranking(session, profile="balanced")
        assert archived_ranking.counts["all"] == 0

        restore_instrument(session, ranking.top_three[0].instrument_id)
        session.commit()
        restored_run = latest_run(session, profile="balanced")
        assert restored_run is not None
        assert restored_run.id > archived_run.id
        restored_ranking = get_ranking(session, profile="balanced")
        assert restored_ranking.counts["all"] == 2

        archive_instrument(session, ranking.top_three[0].instrument_id)
        purged = purge_instrument(
            session,
            ranking.top_three[0].instrument_id,
            confirmation=ranking.top_three[0].name,
        )
        session.commit()
        assert purged.deleted_reports == 1
        assert purged.deleted_listings == 2
        assert session.scalar(select(func.count()).select_from(Instrument)) == 0
        assert session.scalar(select(func.count()).select_from(Listing)) == 0
        assert session.scalar(select(func.count()).select_from(ValuationReport)) == 0
        assert session.scalar(select(func.count()).select_from(ValuationMarket)) == 0
        assert session.scalar(select(func.count()).select_from(RankingEntry)) == 0
        assert get_ranking(session, profile="balanced").counts["all"] == 0


def test_schema_1_2_candidate_persists_presentation(tmp_path: Path) -> None:
    source_card = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
    validate_card(source_card)

    engine = create_engine(f"sqlite:///{tmp_path / 'schema-1-2.db'}")
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
        assert report.schema_version == "1.2"
        assert report.detail_json == source_card["presentation"]

        detail = get_valuation_detail(session, report.markets[0].id)
        assert detail.report_detail["sections"][0]["blocks"][0]["type"] == "gauges"


def test_schema_1_1_rejects_missing_quality_grid() -> None:
    card = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
    card["schema_version"] = "1.1"
    card["markets"] = [card["markets"][0]]
    card["codes"] = {"A": card["markets"][0]["code"]}
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

    with pytest.raises(CardValidationError, match="质量 grid"):
        validate_card(card)


def test_legacy_quality_scorecard_is_canonicalized_to_grid() -> None:
    card = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
    card["schema_version"] = "1.1"
    card["markets"] = [card["markets"][0]]
    card["codes"] = {"A": card["markets"][0]["code"]}
    card["presentation"] = {
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
                        "dimensions": [
                            {
                                "key": "profit_cash_quality",
                                "label": "利润现金含量",
                                "score": 8,
                                "indicator": "经营现金流 / 净利润",
                                "value": "1.2 倍",
                                "assessment": "真实",
                            },
                            {
                                "key": "balance_sheet",
                                "label": "资产负债表",
                                "score": 8,
                                "indicator": "有息负债率",
                                "value": "20%",
                                "assessment": "稳健",
                            },
                            {
                                "key": "roe",
                                "label": "ROE 水平",
                                "score": 7,
                                "indicator": "ROE",
                                "value": "12%",
                                "assessment": "中上",
                            },
                            {
                                "key": "moat",
                                "label": "护城河强度",
                                "score": 8,
                                "indicator": "护城河",
                                "value": "规模",
                                "assessment": "强",
                            },
                            {
                                "key": "survival",
                                "label": "生存能力",
                                "score": 7,
                                "indicator": "压力测试",
                                "value": "通过",
                                "assessment": "通过",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    validate_card(card)
    block = card["presentation"]["sections"][0]["blocks"][0]
    assert block["type"] == "grid"
    assert len(block["columns"]) == 2
    table = next(
        item
        for column in block["columns"]
        for item in column
        if item["type"] == "table"
    )
    assert table["headers"] == ["结果", "评价"]
    assert table["rows"][0] == ["1.2 倍", "真实"]


def test_schema_1_1_ah_requires_split_market_sections() -> None:
    card = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
    card["schema_version"] = "1.1"
    card["presentation"] = _quality_presentation()

    with pytest.raises(CardValidationError, match="dashboard-A"):
        validate_card(card)


def _quality_presentation() -> dict:
    return {
        "schema_version": "1.0",
        "sections": [
            {
                "id": "quality",
                "title": "标的质地",
                "market": "common",
                "blocks": [
                    {
                        "type": "grid",
                        "columns": [
                            [
                                {
                                    "type": "scores",
                                    "items": [
                                        {
                                            "label": label,
                                            "score": "8.0",
                                            "width": 80,
                                            "tone": "positive",
                                        }
                                        for label in (
                                            "利润现金含量",
                                            "资产负债表",
                                            "ROE 水平",
                                            "护城河强度",
                                            "生存能力",
                                        )
                                    ],
                                }
                            ],
                            [
                                {
                                    "type": "table",
                                    "headers": ["维度", "结果", "评价"],
                                    "rows": [
                                        ["指标 1", "结果 1", "评价 1"],
                                        ["指标 2", "结果 2", "评价 2"],
                                        ["指标 3", "结果 3", "评价 3"],
                                        ["指标 4", "结果 4", "评价 4"],
                                        ["指标 5", "结果 5", "评价 5"],
                                    ],
                                }
                            ],
                        ],
                    }
                ],
            }
        ],
    }
