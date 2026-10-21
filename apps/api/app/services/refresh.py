from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.models import Instrument, Listing, QuoteObservation
from app.providers.tencent import ListingRef, QuoteBatch, QuoteData, TencentQuoteProvider
from app.services.macro import load_common_macro
from app.services.ranking import RankingService


@dataclass(frozen=True)
class RefreshSummary:
    listings: int
    quotes_fetched: int
    quotes_saved: int
    quotes_unchanged: int
    quote_errors: list[str]
    macro_observations: int
    ranking_runs: int
    ranking_reused: bool
    latest_quote_at: datetime | None


class QuoteProvider(Protocol):
    def fetch(self, listings: list[ListingRef]) -> QuoteBatch: ...


def refresh_market_data(
    session: Session,
    settings: Settings,
    provider: QuoteProvider | None = None,
    on_phase: Callable[[str], None] | None = None,
) -> RefreshSummary:
    listings = session.scalars(
        select(Listing)
        .join(Instrument, Instrument.id == Listing.instrument_id)
        .where(Listing.enabled.is_(True), Instrument.enabled.is_(True))
        .options(selectinload(Listing.instrument))
        .order_by(Listing.market, Listing.code)
    ).all()
    refs = [
        ListingRef(listing_id=listing.id, market=listing.market, code=listing.code)
        for listing in listings
    ]
    quote_provider = provider or TencentQuoteProvider()
    batch = quote_provider.fetch(refs)
    if on_phase:
        on_phase("saving_quotes")
    saved = 0
    unchanged = 0
    for quote in batch.quotes:
        if _save_quote(session, quote):
            saved += 1
        else:
            unchanged += 1

    if on_phase:
        on_phase("loading_macro")
    macro_count = load_common_macro(session, settings.legacy_common_dir)
    session.flush()
    ranking_runs = 0
    data_changed = saved > 0 or macro_count > 0
    if data_changed:
        if on_phase:
            on_phase("rebuilding_ranking")
        ranking_runs = RankingService().rebuild(session)
    elif on_phase:
        on_phase("finalizing")
    return RefreshSummary(
        listings=len(listings),
        quotes_fetched=len(batch.quotes),
        quotes_saved=saved,
        quotes_unchanged=unchanged,
        quote_errors=batch.errors,
        macro_observations=macro_count,
        ranking_runs=ranking_runs,
        ranking_reused=not data_changed,
        latest_quote_at=max(
            (quote.observed_at for quote in batch.quotes),
            default=None,
        ),
    )


def _save_quote(session: Session, quote: QuoteData) -> bool:
    existing = session.scalar(
        select(QuoteObservation).where(
            QuoteObservation.listing_id == quote.listing_id,
            QuoteObservation.source == "tencent",
            QuoteObservation.observed_at == quote.observed_at,
        )
    )
    if existing is not None:
        return False
    session.add(
        QuoteObservation(
            listing_id=quote.listing_id,
            observed_at=quote.observed_at,
            quote_date=quote.quote_date,
            price=quote.price,
            previous_close=quote.previous_close,
            change_pct=quote.change_pct,
            pe=quote.pe,
            pb=quote.pb,
            source="tencent",
            source_name=quote.source_name,
            raw=quote.raw,
        )
    )
    return True
