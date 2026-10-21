from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.services.importer import import_legacy_cards
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
