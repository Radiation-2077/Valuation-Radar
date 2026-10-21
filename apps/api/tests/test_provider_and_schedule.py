from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import JobRun, ScheduleSetting
from app.providers.tencent import ListingRef, TencentQuoteProvider, tencent_symbol
from app.services.schedule import is_due, next_run_at, scheduler_tick

CHINA_TZ = ZoneInfo("Asia/Shanghai")


def _fields(**values: tuple[int, str]) -> list[str]:
    fields = [""] * 65
    for index, value in values.values():
        fields[index] = value
    return fields


def test_tencent_symbol_mapping() -> None:
    assert tencent_symbol("A", "600941.SH") == "sh600941"
    assert tencent_symbol("A", "300750.SZ") == "sz300750"
    assert tencent_symbol("H", "00941.HK") == "hk00941"
    assert tencent_symbol("CN", "159202") == "sz159202"


def test_tencent_provider_parses_a_and_h_fields() -> None:
    a_fields = _fields(
        name=(1, "中国移动"),
        price=(3, "96.59"),
        previous=(4, "101.77"),
        timestamp=(30, "20261021161443"),
        change=(32, "-5.09"),
        pe=(39, "16.38"),
        pb=(46, "1.50"),
    )
    h_fields = _fields(
        name=(1, "中国移动"),
        price=(3, "77.550"),
        previous=(4, "80.500"),
        timestamp=(30, "2026/10/21 16:08:25"),
        change=(32, "-3.66"),
        pe=(57, "11.08"),
        pb=(58, "6.99"),
        wrong_a_pb=(46, "CHINA MOBILE"),
    )
    body = (
        f'v_sh600941="{"~".join(a_fields)}";\n'
        f'v_hk00941="{"~".join(h_fields)}";\n'
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body.encode("gbk"))

    provider = TencentQuoteProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    batch = provider.fetch(
        [
            ListingRef(1, "A", "600941.SH"),
            ListingRef(2, "H", "00941.HK"),
        ]
    )

    assert not batch.errors
    assert [quote.price for quote in batch.quotes] == [96.59, 77.55]
    assert batch.quotes[0].pe == 16.38
    assert batch.quotes[0].pb == 1.5
    assert batch.quotes[1].pe == 11.08
    assert batch.quotes[1].pb == 6.99


def test_trading_day_schedule_is_due_and_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        schedule = ScheduleSetting(run_time="18:30", enabled=True)
        session.add(schedule)
        session.commit()

        before = datetime(2026, 10, 21, 18, 0, tzinfo=CHINA_TZ)
        after = datetime(2026, 10, 21, 19, 0, tzinfo=CHINA_TZ)
        assert is_due(schedule, before) is False
        assert is_due(schedule, after) is True
        assert next_run_at(schedule, before) == datetime(
            2026, 10, 21, 18, 30, tzinfo=CHINA_TZ
        )

        first = scheduler_tick(session, after)
        session.commit()
        second = scheduler_tick(session, after)
        session.commit()

        assert first is not None
        assert second is None
        assert session.query(JobRun).count() == 1


def test_manual_schedule_never_runs_automatically() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        schedule = ScheduleSetting(frequency="manual", enabled=True)
        session.add(schedule)
        session.commit()

        now = datetime(2026, 10, 21, 22, 0, tzinfo=CHINA_TZ)
        assert is_due(schedule, now) is False
        assert next_run_at(schedule, now) is None
