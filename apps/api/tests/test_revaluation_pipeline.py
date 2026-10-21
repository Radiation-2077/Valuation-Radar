from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.integrations.codex import CodexResult
from app.models import Instrument, JobRun, ValuationReport
from app.services.importer import import_legacy_cards
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


def test_codex_candidate_requires_review_before_ranking(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(
        storage_root=tmp_path / "storage",
        timezone="Asia/Shanghai",
    )

    with Session(engine) as session:
        import_legacy_cards(
            session,
            data_dir=LEGACY_DATA_DIR,
            settings=settings,
        )
        instrument = session.scalar(select(Instrument).where(Instrument.name == "中国移动"))
        assert instrument is not None
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
            executor=FakeCodexExecutor(settings),  # type: ignore[arg-type]
        )
        assert report.status == "needs_review"
        assert report.source == "codex"
        assert session.get(Instrument, instrument.id).verdict == original_verdict  # type: ignore[union-attr]
        assert [item.id for item in list_review_reports(session)] == [report.id]

        published = approve_review(session, report.id)
        assert published.status == "published"
        assert session.get(Instrument, instrument.id).verdict == "观望等待"  # type: ignore[union-attr]
        assert session.query(ValuationReport).filter_by(status="needs_review").count() == 0
        assert session.query(ValuationReport).filter_by(status="published").count() > 0
