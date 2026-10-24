from __future__ import annotations

import importlib.util
import json
import os
from datetime import date
from pathlib import Path

import pytest

from app.domain.scoring import PROFILES, context_from_card, score_context

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_EXAMPLE = (
    PROJECT_ROOT
    / "schemas"
    / "value-investing"
    / "examples"
    / "card-v1.2.example.json"
)
SKILL_RANK = (
    Path(os.getenv("CODEX_HOME", Path.home() / ".codex"))
    / "skills"
    / "investment-ranking"
    / "scripts"
    / "rank.py"
)


@pytest.mark.skipif(
    not SKILL_RANK.is_file(),
    reason="需要 investment-ranking skill",
)
def test_scores_match_investment_ranking_skill() -> None:
    spec = importlib.util.spec_from_file_location("skill_rank", SKILL_RANK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    latest_cards = [json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))]
    for card in latest_cards:
        for market in card["markets"]:
            market["gauges"] = {"certainty": market["certainty"]}
    expected = {
        (entry["name"], entry["market"]): entry
        for entry in module.build_entries(latest_cards, date.today())
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
        profile_key = f"score::{profile.code}"
        for entry in actual:
            reference = expected[(entry.context.name, entry.context.market)]
            assert entry.scores[profile.code] == pytest.approx(reference[profile_key])
