from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
CHINA_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class ListingRef:
    listing_id: int
    market: str
    code: str


@dataclass(frozen=True)
class QuoteData:
    listing_id: int
    observed_at: datetime
    quote_date: date
    price: float
    previous_close: float | None
    change_pct: float | None
    pe: float | None
    pb: float | None
    source_name: str
    raw: dict[str, Any]


@dataclass
class QuoteBatch:
    quotes: list[QuoteData] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class TencentQuoteProvider:
    source = "tencent"

    def __init__(self, client: httpx.Client | None = None, batch_size: int = 20) -> None:
        self.client = client or httpx.Client(
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 ValuationRadar/0.1",
                "Accept": "*/*",
            },
        )
        self.batch_size = batch_size

    def fetch(self, listings: list[ListingRef]) -> QuoteBatch:
        batch = QuoteBatch()
        symbols = {
            listing.listing_id: tencent_symbol(listing.market, listing.code)
            for listing in listings
        }
        by_symbol = {symbol: listing_id for listing_id, symbol in symbols.items()}

        for start in range(0, len(listings), self.batch_size):
            chunk = list(symbols.values())[start : start + self.batch_size]
            try:
                response = self.client.get(f"{TENCENT_QUOTE_URL}{','.join(chunk)}")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                batch.errors.append(f"腾讯批量行情请求失败：{exc}")
                continue

            text = response.content.decode("gbk", errors="replace")
            for symbol, payload in parse_tencent_response(text):
                listing_id = by_symbol.get(symbol)
                if listing_id is None:
                    continue
                try:
                    batch.quotes.append(parse_quote(listing_id, symbol, payload))
                except (IndexError, TypeError, ValueError) as exc:
                    batch.errors.append(f"{symbol} 字段解析失败：{exc}")
        return batch


def tencent_symbol(market: str, code: str) -> str:
    normalized_market = market.upper()
    normalized_code = code.upper()
    raw_code, _, suffix = normalized_code.partition(".")
    market = normalized_market or suffix
    if market == "H" or suffix == "HK":
        return f"hk{raw_code.zfill(5)}"
    if suffix == "SH":
        return f"sh{raw_code}"
    if suffix == "SZ":
        return f"sz{raw_code}"
    if suffix == "BJ":
        return f"bj{raw_code}"
    if raw_code.startswith(("5", "6", "9")):
        return f"sh{raw_code}"
    if raw_code.startswith(("0", "1", "2", "3")):
        return f"sz{raw_code}"
    return f"bj{raw_code}"


def parse_tencent_response(text: str) -> list[tuple[str, list[str]]]:
    parsed: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if '="' not in line:
            continue
        variable, payload = line.split('="', 1)
        symbol = variable.removeprefix("v_").strip()
        values = payload.rstrip('";').split("~")
        if len(values) < 4 or not values[3]:
            continue
        parsed.append((symbol, values))
    return parsed


def parse_quote(listing_id: int, symbol: str, values: list[str]) -> QuoteData:
    is_hk = symbol.startswith("hk")
    observed_at = _parse_quote_time(values[30])
    pe_index = 57 if is_hk else 39
    pb_index = 58 if is_hk else 46
    return QuoteData(
        listing_id=listing_id,
        observed_at=observed_at,
        quote_date=observed_at.astimezone(CHINA_TZ).date(),
        price=_required_float(values[3]),
        previous_close=_optional_float(values[4]),
        change_pct=_optional_float(values[32]),
        pe=_indexed_float(values, pe_index),
        pb=_indexed_float(values, pb_index),
        source_name=values[1],
        raw={str(index): value for index, value in enumerate(values)},
    )


def _parse_quote_time(value: str) -> datetime:
    if "/" in value:
        parsed = datetime.strptime(value, "%Y/%m/%d %H:%M:%S").replace(tzinfo=CHINA_TZ)
    else:
        parsed = datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=CHINA_TZ)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _required_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError("价格必须为正数")
    return number


def _optional_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _indexed_float(values: list[str], index: int) -> float | None:
    if index >= len(values):
        return None
    return _optional_float(values[index])
