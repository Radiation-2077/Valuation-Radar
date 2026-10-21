from __future__ import annotations

import importlib.util
import json
import os
from datetime import date
from pathlib import Path

import pytest

from app.domain.scoring import PROFILES, context_from_card, score_context

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LEGACY_DATA_DIR = PROJECT_ROOT.parent / "data"
SKILL_RANK = (
    Path(os.getenv("CODEX_HOME", Path.home() / ".codex"))
    / "skills"
    / "investment-ranking"
    / "scripts"
    / "rank.py"
)


@pytest.mark.skipif(
    not LEGACY_DATA_DIR.is_dir() or not SKILL_RANK.is_file(),
    reason="需要现有数据卡和 investment-ranking skill",
)
def test_scores_match_investment_ranking_skill() -> None:
    spec = importlib.util.spec_from_file_location("skill_rank", SKILL_RANK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cards: list[dict] = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(LEGACY_DATA_DIR.glob("*.json"))
    ]
    latest: dict[str, tuple[tuple[str, str], dict]] = {}
    for card in cards:
        candidate_key = (card["analysis_date"], card.get("generated_at") or "")
        current = latest.get(card["name"])
        if current is None or candidate_key > current[0]:
            latest[card["name"]] = (candidate_key, card)
    latest_cards = [item[1] for item in latest.values()]
    expected = {
        (entry["name"], entry["market"]): entry
        for entry in module.build_entries(latest_cards)
    }
    actual = [
        score_context(
            context_from_card(
                card,
                market,
                date.fromisoformat(card["analysis_date"]),
            )
        )
        for card in latest_cards
        for market in card["markets"]
    ]

    for profile in PROFILES.values():
        profile_key = f"score::{profile.label}"
        for entry in actual:
            reference = expected[(entry.context.name, entry.context.market)]
            assert entry.scores[profile.code] == pytest.approx(reference[profile_key])
