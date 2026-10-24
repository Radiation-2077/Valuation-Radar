from __future__ import annotations

from collections.abc import Generator
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Instrument, JobRun
from app.services.revaluation import _prompt


def test_create_instrument_queues_valuation(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'instruments.db'}")
    Base.metadata.create_all(engine)

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/instruments",
            json={"name": "测试银行", "code": "sh600036", "asset_type": "stock"},
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["market"] == "A"
        assert payload["code"] == "600036.SH"
        assert payload["status"] == "queued"

        with Session(engine) as session:
            job = session.get(JobRun, payload["job_id"])
            assert job is not None
            assert job.job_type == "valuation_refresh"
            assert job.scope == f"instrument:{payload['instrument_id']}"
            assert job.details["instrument"] == "测试银行"

        duplicate = client.post(
            "/api/v1/instruments",
            json={"name": "另一银行", "code": "600036.SH", "asset_type": "stock"},
        )
        assert duplicate.status_code == 409

        etf = client.post(
            "/api/v1/instruments",
            json={"name": "测试ETF", "code": "510300", "asset_type": "etf"},
        )
        assert etf.status_code == 202
        assert etf.json()["market"] == "CN"
        assert etf.json()["code"] == "510300.SH"

        no_code = client.post(
            "/api/v1/instruments",
            json={"name": "仅名称标的", "asset_type": "stock"},
        )
        assert no_code.status_code == 202
        assert no_code.json()["market"] is None
        assert no_code.json()["code"] is None

        invalid = client.post(
            "/api/v1/instruments",
            json={"name": "无效代码", "code": "ABC", "asset_type": "stock"},
        )
        assert invalid.status_code == 422

        instrument_id = payload["instrument_id"]
        blocked = client.delete(f"/api/v1/instruments/{instrument_id}")
        assert blocked.status_code == 409
        assert "任务" in blocked.json()["detail"]["message"]

        with Session(engine) as session:
            job = session.get(JobRun, payload["job_id"])
            assert job is not None
            job.status = "failed"
            session.commit()

        archived = client.delete(f"/api/v1/instruments/{instrument_id}")
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        assert archived.json()["archived_at"] is not None

        listed = client.get("/api/v1/instruments").json()["items"]
        archived_item = next(item for item in listed if item["id"] == instrument_id)
        assert archived_item["enabled"] is False
        assert archived_item["archive_reason"] == "手动移出标的库"
        assert archived_item["listings"][0]["enabled"] is False

        revaluation = client.post(f"/api/v1/instruments/{instrument_id}/revaluations")
        assert revaluation.status_code == 409

        restored = client.post(f"/api/v1/instruments/{instrument_id}/restore")
        assert restored.status_code == 200
        assert restored.json()["status"] == "active"
        assert restored.json()["archived_at"] is None

        client.delete(f"/api/v1/instruments/{instrument_id}")
        rejected_purge = client.delete(
            f"/api/v1/instruments/{instrument_id}/purge",
            params={"confirmation": "错误名称"},
        )
        assert rejected_purge.status_code == 409

        purged = client.delete(
            f"/api/v1/instruments/{instrument_id}/purge",
            params={"confirmation": "测试银行"},
        )
        assert purged.status_code == 200
        assert purged.json()["deleted_listings"] == 1
        assert purged.json()["deleted_jobs"] == 1
        with Session(engine) as session:
            assert session.get(JobRun, payload["job_id"]) is None
    finally:
        app.dependency_overrides.clear()


def test_name_only_prompt_requires_dual_market_discovery() -> None:
    prompt = _prompt(
        Instrument(name="示例公司", asset_type="stock", path="stable"),
        {"listings": []},
        date(2026, 10, 24),
        "示例公司_2026-10-24.json",
        has_previous_card=False,
    )

    assert "按标的名检索上市代码" in prompt
    assert "A/H 两地上市" in prompt
    assert "默认完整调研两个市场" in prompt
    assert "industry_lifecycle" in prompt
    assert "industry_cycle" in prompt
    assert "substitution" in prompt
    assert "explanation" in prompt


def test_single_side_code_prompt_still_requires_dual_market_check() -> None:
    prompt = _prompt(
        Instrument(name="示例公司", asset_type="stock", path="stable"),
        {"listings": [{"market": "A", "code": "600000.SH"}]},
        date(2026, 10, 24),
        "示例公司_2026-10-24.json",
        has_previous_card=True,
    )

    assert "仍须核实是否存在另一地上市" in prompt
    assert "A/H 两地上市，默认完整调研两个市场" in prompt
