from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.domain.scoring import ALGORITHM_VERSION, DEFAULT_PROFILE, PROFILES
from app.models import ValuationMarket
from app.schemas.api import (
    InstrumentListOut,
    MetaResponse,
    ProfileOut,
    RankingResponse,
    ValuationDetailOut,
)
from app.services.queries import (
    get_ranking,
    get_valuation_detail,
    list_instruments,
)

router = APIRouter(prefix="/api/v1")
SessionDep = Annotated[Session, Depends(get_db)]
ProfileQuery = Annotated[str, Query()]


@router.get("/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    return MetaResponse(
        profiles=[
            ProfileOut(
                code=profile.code,
                label=profile.label,
                description=profile.description,
                weights={
                    "margin": profile.margin,
                    "base": profile.base,
                    "risk": profile.risk,
                    "stability": profile.stability,
                },
            )
            for profile in PROFILES.values()
        ],
        default_profile=DEFAULT_PROFILE,
        algorithm_version=ALGORITHM_VERSION,
    )


@router.get("/dashboard", response_model=RankingResponse)
def dashboard(
    session: SessionDep,
    profile: ProfileQuery = DEFAULT_PROFILE,
    market: str | None = None,
    path: str | None = None,
    industry: str | None = None,
    stale_only: bool = False,
) -> RankingResponse:
    return get_ranking(
        session,
        profile=profile,
        market=market,
        path=path,
        industry=industry,
        stale_only=stale_only,
    )


@router.get("/rankings", response_model=RankingResponse)
def rankings(
    session: SessionDep,
    profile: ProfileQuery = DEFAULT_PROFILE,
    market: str | None = None,
    path: str | None = None,
    industry: str | None = None,
    stale_only: bool = False,
) -> RankingResponse:
    return get_ranking(
        session,
        profile=profile,
        market=market,
        path=path,
        industry=industry,
        stale_only=stale_only,
    )


@router.get("/valuations/{valuation_market_id}", response_model=ValuationDetailOut)
def valuation_detail(
    valuation_market_id: int,
    session: SessionDep,
    profile: ProfileQuery = DEFAULT_PROFILE,
) -> ValuationDetailOut:
    return get_valuation_detail(session, valuation_market_id, profile)


@router.get("/valuations/{valuation_market_id}/report")
def valuation_report(
    valuation_market_id: int,
    session: SessionDep,
) -> FileResponse:
    market = session.scalar(
        select(ValuationMarket).where(ValuationMarket.id == valuation_market_id)
    )
    if market is None or market.report is None or not market.report.report_path:
        raise HTTPException(status_code=404, detail={"message": "原报告不存在"})
    settings = get_settings()
    path = (settings.storage_root / market.report.report_path).resolve()
    artifacts_root = settings.artifacts_dir.resolve()
    if not path.is_relative_to(artifacts_root) or not path.is_file():
        raise HTTPException(status_code=404, detail={"message": "原报告文件不存在"})
    return FileResponse(
        path,
        media_type="text/html",
        headers={
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'"
        },
    )


@router.get("/instruments", response_model=InstrumentListOut)
def instruments(session: SessionDep) -> InstrumentListOut:
    return list_instruments(session)
