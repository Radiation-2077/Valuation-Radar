from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument, JobRun, Listing
from app.services.schedule import queue_job

_PREFIXED_CODE = re.compile(r"^(SH|SZ|BJ|HK)(\d{5,6})$")
_SUFFIXED_CODE = re.compile(r"^(\d{5,6})\.(SH|SZ|BJ|HK)$")


class InstrumentConflictError(ValueError):
    pass


def normalize_listing(code: str, asset_type: str) -> tuple[str, str, str]:
    raw = code.strip().upper().replace(" ", "")
    match = _PREFIXED_CODE.fullmatch(raw)
    if match:
        prefix, digits = match.groups()
        raw = f"{digits}.{prefix}"
    match = _SUFFIXED_CODE.fullmatch(raw)
    if match:
        digits, suffix = match.groups()
    elif re.fullmatch(r"\d{6}", raw):
        digits = raw
        suffix = (
            "SH"
            if raw.startswith(("5", "6", "9"))
            else "SZ"
            if raw.startswith(("0", "1", "2", "3"))
            else "BJ"
        )
    elif re.fullmatch(r"\d{5}", raw):
        digits = raw
        suffix = "HK"
    else:
        raise ValueError(
            "证券代码格式不支持，请使用 600036、600036.SH、sh600036 或 00700.HK"
        )

    if suffix == "HK":
        return "H", f"{digits.zfill(5)}.HK", "HKD"
    market = "CN" if asset_type == "etf" else "A"
    return market, f"{digits}.{suffix}", "CNY"


def create_instrument_and_queue(
    session: Session,
    *,
    name: str,
    code: str | None,
    asset_type: str,
) -> tuple[Instrument, Listing | None, JobRun]:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("标的名称不能为空")
    if asset_type not in {"stock", "etf"}:
        raise ValueError("资产类型必须是 stock 或 etf")

    listing: Listing | None = None
    listing_spec: tuple[str, str, str] | None = None
    if code and code.strip():
        market, normalized_code, currency = normalize_listing(code, asset_type)
        listing_spec = (market, normalized_code, currency)
        existing_listing = session.scalar(
            select(Listing).where(
                Listing.market == market,
                Listing.code == normalized_code,
            )
        )
        if existing_listing is not None:
            raise InstrumentConflictError(
                f"{market} {normalized_code} 已存在，无需重复添加"
            )
    existing_name = session.scalar(
        select(Instrument).where(Instrument.name == normalized_name)
    )
    if existing_name is not None:
        raise InstrumentConflictError(f"标的名 {normalized_name} 已存在")

    instrument = Instrument(
        name=normalized_name,
        asset_type=asset_type,
        path="etf" if asset_type == "etf" else "stable",
        industry="",
        cycle_stage="待估值",
    )
    session.add(instrument)
    session.flush()
    if listing_spec is not None:
        market, normalized_code, currency = listing_spec
        listing = Listing(
            instrument_id=instrument.id,
            market=market,
            code=normalized_code,
            currency=currency,
        )
        session.add(listing)
        session.flush()
    job, _ = queue_job(
        session,
        job_type="valuation_refresh",
        trigger="manual",
        scope=f"instrument:{instrument.id}",
        idempotency_key=f"valuation-refresh:{instrument.id}:{uuid.uuid4()}",
    )
    job.details = {**(job.details or {}), "instrument": instrument.name}
    return instrument, listing, job
