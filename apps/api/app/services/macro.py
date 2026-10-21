from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MacroObservation


def load_common_macro(session: Session, common_dir: Path) -> int:
    if not common_dir.is_dir():
        return 0
    imported = 0
    for path in sorted(common_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        observed_at = _parse_datetime(payload.get("updated_at"))
        unit = str(payload.get("unit") or "")
        for key, item in (payload.get("items") or {}).items():
            value = item.get("value")
            as_of = item.get("as_of")
            if not isinstance(value, (int, float)) or not isinstance(as_of, str):
                continue
            source = str(item.get("source") or payload.get("source") or path.stem)
            existing = session.scalar(
                select(MacroObservation).where(
                    MacroObservation.key == key,
                    MacroObservation.source == source,
                    MacroObservation.as_of == date.fromisoformat(as_of),
                )
            )
            if existing is not None:
                continue
            session.add(
                MacroObservation(
                    key=key,
                    as_of=date.fromisoformat(as_of),
                    observed_at=observed_at,
                    value=float(value),
                    unit=unit,
                    source=source,
                    raw=dict(item),
                )
            )
            imported += 1
    session.flush()
    return imported


def latest_macro_values(session: Session) -> dict[str, float]:
    rows = session.scalars(
        select(MacroObservation).order_by(
            MacroObservation.observed_at.desc(),
            MacroObservation.id.desc(),
        )
    ).all()
    values: dict[str, float] = {}
    for row in rows:
        values.setdefault(row.key, row.value)
    return values


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    return datetime.now(UTC).replace(tzinfo=None)
