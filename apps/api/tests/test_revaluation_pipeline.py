from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.integrations.codex import CodexResult
from app.models import AiRun, Instrument, JobRun, Listing, ValuationMarket, ValuationReport
from app.services.importer import import_legacy_cards
from app.services.queries import get_ranking, get_valuation_detail
from app.services.revaluation import run_valuation_refresh
from app.services.reviews import approve_review, list_review_reports

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LEGACY_DATA_DIR = PROJECT_ROOT.parent / "data"


class FakeCodexExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        cwd: Path,
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
    ) -> CodexResult:
        del prompt, output_schema
        card = json.loads((cwd / "previous_card.json").read_text(encoding="utf-8"))
        analysis_date = datetime.now(ZoneInfo(self.settings.timezone)).date()
        card["analysis_date"] = analysis_date.isoformat()
        card["generated_at"] = datetime.now(ZoneInfo(self.settings.timezone)).isoformat()
        card["conclusion"]["verdict"] = "观望等待"
        card["schema_version"] = "1.1"
        card["presentation"] = _quality_presentation()
        card_path = cwd / "data" / f"{card['name']}_{analysis_date.isoformat()}.json"
        card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "data_card_path": str(card_path),
                    "summary": "fake",
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        stdout_path = cwd / "fake.stdout"
        stderr_path = cwd / "fake.stderr"
        stdout_path.write_text("{}", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return CodexResult(
            exit_code=0,
            version="codex-fake 1.0",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            manifest_path=manifest_path,
        )


class FailingCodexExecutor:
    def run(
        self,
        cwd: Path,
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
    ) -> CodexResult:
        del prompt, output_schema, manifest_path
        stdout_path = cwd / "failed.stdout"
        stderr_path = cwd / "failed.stderr"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("sandbox and approval options conflict", encoding="utf-8")
        return CodexResult(
            exit_code=2,
            version="codex-fake 1.0",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            manifest_path=cwd / "missing-manifest.json",
        )


def test_codex_candidate_requires_review_before_ranking(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )

    with Session(engine, autoflush=False) as session:
        import_legacy_cards(
            session,
            data_dir=LEGACY_DATA_DIR,
            settings=settings,
        )
        instrument = session.scalar(select(Instrument).where(Instrument.name == "中国移动"))
        assert instrument is not None
        old_market_id, old_market_name = session.execute(
            select(ValuationMarket.id, Listing.market)
            .join(ValuationReport, ValuationReport.id == ValuationMarket.report_id)
            .join(Listing, Listing.id == ValuationMarket.listing_id)
            .where(ValuationReport.instrument_id == instrument.id)
            .order_by(ValuationReport.analysis_date, ValuationReport.revision)
            .limit(1)
        ).one()
        original_verdict = instrument.verdict
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="running",
            idempotency_key="candidate-test",
        )
        session.add(job)
        session.commit()

        report = run_valuation_refresh(
            session,
            job,
            settings,
            executor=FakeCodexExecutor(settings),
        )
        assert report.status == "needs_review"
        assert report.source == "codex"
        assert session.get(Instrument, instrument.id).verdict == original_verdict  # type: ignore[union-attr]
        assert [item.id for item in list_review_reports(session)] == [report.id]
        candidate_detail = get_valuation_detail(session, report.markets[0].id)
        assert candidate_detail.latest_valuation_market_id == report.markets[0].id
        session.refresh(job)
        assert any(
            "Codex 子进程" in event["message"]
            for event in job.details["debug_events"]
        )

        published = approve_review(session, report.id)
        assert published.status == "published"
        assert session.get(Instrument, instrument.id).verdict == "观望等待"  # type: ignore[union-attr]
        assert session.query(ValuationReport).filter_by(status="needs_review").count() == 0
        assert session.query(ValuationReport).filter_by(status="published").count() > 0
        ranking = get_ranking(session, profile="balanced")
        ranked = next(
            item
            for item in ranking.main_board
            if item.name == "中国移动" and item.market == "A"
        )
        assert ranked.report_id == published.id
        assert ranked.valuation_market_id in {market.id for market in published.markets}
        detail = get_valuation_detail(session, published.markets[0].id)
        assert detail.report_detail["sections"][0]["blocks"][0]["type"] == "grid"
        old_detail = get_valuation_detail(session, old_market_id)
        assert old_detail.valuation_market_id == old_market_id
        latest_market_id = next(
            market.id
            for market in published.markets
            if market.listing.market == old_market_name
        )
        assert old_detail.latest_valuation_market_id == latest_market_id


def test_codex_failure_keeps_published_valuation(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate-failure.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )

    with Session(engine) as session:
        import_legacy_cards(session, data_dir=LEGACY_DATA_DIR, settings=settings)
        instrument = session.scalar(select(Instrument).where(Instrument.name == "中国移动"))
        assert instrument is not None
        original_verdict = instrument.verdict
        published_before = session.query(ValuationReport).filter_by(
            instrument_id=instrument.id,
            status="published",
        ).count()
        job = JobRun(
            job_type="valuation_refresh",
            trigger="manual",
            scope=f"instrument:{instrument.id}",
            status="running",
            phase="valuing",
            idempotency_key="candidate-failure-test",
        )
        session.add(job)
        session.commit()

        with pytest.raises(RuntimeError, match="Codex 退出码 2"):
            run_valuation_refresh(
                session,
                job,
                settings,
                executor=FailingCodexExecutor(),
            )

        session.refresh(instrument)
        assert instrument.verdict == original_verdict
        assert session.query(ValuationReport).filter_by(
            instrument_id=instrument.id,
            status="published",
        ).count() == published_before
        assert session.query(ValuationReport).filter_by(status="needs_review").count() == 0
        failed_run = session.query(AiRun).filter_by(job_id=job.id).one()
        assert failed_run.status == "rejected"
        assert failed_run.exit_code == 2
        assert "sandbox and approval options conflict" in failed_run.stderr
        session.refresh(job)
        assert any(
            "重估失败" in event["message"]
            for event in job.details["debug_events"]
        )


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
    quality_grid = {
        "type": "grid",
        "columns": [
            [
                {"type": "heading", "level": 3, "text": "质量分项（0–10）"},
                {
                    "type": "scores",
                    "items": [
                        {
                            "label": item["label"],
                            "score": f"{item['score']:.1f}",
                            "width": item["score"] * 10,
                            "tone": "positive",
                        }
                        for item in dimensions
                    ],
                },
            ],
            [
                {"type": "heading", "level": 3, "text": "关键指标"},
                {
                    "type": "table",
                    "headers": ["维度", "结果", "评价"],
                    "rows": [
                        [item["indicator"], item["value"], item["assessment"]]
                        for item in dimensions
                    ],
                },
            ],
        ],
    }
    sections = [
        {
            "id": "quality",
            "title": "标的质地",
            "market": "common",
            "blocks": [
                    quality_grid,
                {
                    "type": "callout",
                    "tone": "info",
                    "title": "本章小结",
                    "body": "质量可接受。",
                    "summary": True,
                },
            ],
        }
    ]
    for section_id, market, title in (
        ("dashboard-A", "A", "A 股结论"),
        ("dashboard-H", "H", "H 股结论"),
        ("cycle", "common", "产业周期"),
        ("cross_market", "common", "A/H 溢价"),
        ("valuation-A", "A", "A 股估值"),
        ("valuation-H", "H", "H 股估值"),
        ("position-A", "A", "A 股仓位"),
        ("position-H", "H", "H 股仓位"),
        ("expected_return-A", "A", "A 股预期收益"),
        ("expected_return-H", "H", "H 股预期收益"),
        ("risks-A", "A", "A 股风险"),
        ("risks-H", "H", "H 股风险"),
        ("conclusion-A", "A", "A 股结论"),
        ("conclusion-H", "H", "H 股结论"),
        ("sources", "common", "数据来源"),
        ("disclaimer", "common", "免责声明"),
    ):
        sections.append(
            {
                "id": section_id,
                "title": title,
                "market": market,
                "blocks": [
                    {
                        "type": "callout",
                        "tone": "info",
                        "title": "本章小结",
                        "body": title,
                        "summary": section_id not in {"sources", "disclaimer"},
                    }
                ],
            }
        )
    return {"schema_version": "1.0", "sections": sections}
