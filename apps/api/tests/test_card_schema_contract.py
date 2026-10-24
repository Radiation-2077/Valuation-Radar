from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.services.card_contract import CardContractError, validate_v1_2_card
from app.services.importer import validate_card

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    PROJECT_ROOT
    / ".codex"
    / "skills"
    / "value-investing"
    / "references"
    / "card-v1.2.schema.json"
)
EXAMPLE_PATH = (
    PROJECT_ROOT
    / "schemas"
    / "value-investing"
    / "examples"
    / "card-v1.2.example.json"
)
SCORECARD_PATH = (
    PROJECT_ROOT
    / ".codex"
    / "skills"
    / "value-investing"
    / "scripts"
    / "scorecard.py"
)
SCORECARD_SPEC = importlib.util.spec_from_file_location(
    "value_investing_scorecard",
    SCORECARD_PATH,
)
assert SCORECARD_SPEC is not None and SCORECARD_SPEC.loader is not None
SCORECARD = importlib.util.module_from_spec(SCORECARD_SPEC)
SCORECARD_SPEC.loader.exec_module(SCORECARD)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def example() -> dict[str, Any]:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema, format_checker=FormatChecker())


def section(card: dict[str, Any], section_id: str) -> dict[str, Any]:
    return next(
        item
        for item in card["presentation"]["sections"]
        if item["id"] == section_id
    )


def single_market_card(
    example: dict[str, Any],
    *,
    path: str,
    asset_type: str,
    module: str,
    market: str = "A",
    code: str = "600000.SH",
) -> dict[str, Any]:
    card = copy.deepcopy(example)
    card["asset_type"] = asset_type
    card["path"] = path
    card["model_modules"] = [module]
    card["codes"] = {market: code}
    card["markets"] = [copy.deepcopy(card["markets"][0])]
    card["markets"][0]["market"] = market
    card["markets"][0]["code"] = code
    card["markets"][0]["currency"] = "CNY"

    sections = []
    for source in card["presentation"]["sections"]:
        if source["market"] not in {"common", "A"}:
            continue
        if source["role"] == "cross_market":
            continue
        current = copy.deepcopy(source)
        current["market"] = market if current["market"] == "A" else "common"
        current["id"] = current["id"].replace("-a", f"-{market.lower()}")
        for block in current["blocks"]:
            if block.get("market") == "A":
                block["market"] = market
        if current["role"] == "model_analysis":
            current["module"] = module
            current["title"] = module.replace("_", " ").title()
        sections.append(current)
    card["presentation"]["sections"] = sections
    if path == "cyclical":
        section(card, "cycle")["blocks"].insert(
            1,
            {
                "type": "industry_cycle",
                "position": card["cycle_position"],
                "phase": "pullback",
                "direction": "down",
            },
        )
    return card


def add_quality_dimension_column(card: dict[str, Any]) -> None:
    quality_grid = section(card, "quality")["blocks"][0]
    table = next(
        block
        for column in quality_grid["columns"]
        for block in column
        if block["type"] == "table"
    )
    table["columns"].insert(
        0,
        {"key": "metric", "label": "维度", "role": "label"},
    )
    for row in table["rows"]:
        row["metric"] = "重复维度"


def lifecycle_block(card: dict[str, Any]) -> dict[str, Any]:
    return next(
        block
        for block in section(card, "cycle")["blocks"]
        if block["type"] == "industry_lifecycle"
    )


def add_etf_metrics(card: dict[str, Any]) -> tuple[float, float]:
    market = card["markets"][0]
    constituents = [
        {"code": "00001.HK", "name": "示例股票甲", "weight_pct": 40.0, "pb": 0.7},
        {"code": "00002.HK", "name": "示例股票乙", "weight_pct": 30.0, "pb": 0.8},
        {"code": "00003.HK", "name": "示例股票丙", "weight_pct": 20.0, "pb": 1.0},
        {"code": "00004.HK", "name": "示例股票丁", "weight_pct": 10.0, "pb": 8.0},
    ]
    weight_sum = sum(item["weight_pct"] for item in constituents)
    harmonic_pb = weight_sum / sum(
        item["weight_pct"] / item["pb"] for item in constituents
    )
    arithmetic_pb = sum(
        item["weight_pct"] * item["pb"] for item in constituents
    ) / weight_sum
    market["valuation"]["pb"] = round(harmonic_pb, 4)
    market["etf_metrics"] = {
        "index_code": "EXAMPLE",
        "index_name": "示例指数",
        "weight_method": "top10_market_cap_weighted_harmonic",
        "weight_as_of": market["price_date"],
        "weight_source": "测试权重",
        "coverage_pct": weight_sum,
        "pb_as_of": market["price_date"],
        "pb_source": "测试 PB",
        "nav": market["price"],
        "nav_date": market["price_date"],
        "nav_source": "测试净值",
        "premium_discount_pct": 0.0,
        "constituents": constituents,
        "representative_pb": round(harmonic_pb, 4),
    }
    return arithmetic_pb, harmonic_pb


def make_cyclical_without_cycle_chart(card: dict[str, Any]) -> None:
    card["path"] = "cyclical"
    card["model_modules"] = ["normalized_earnings"]
    for item in card["presentation"]["sections"]:
        if item["role"] == "model_analysis":
            item["module"] = "normalized_earnings"


def add_cycle_with_reversed_direction(card: dict[str, Any]) -> None:
    section(card, "cycle")["blocks"].insert(
        1,
        {
            "type": "industry_cycle",
            "position": card["cycle_position"],
            "phase": "recovery",
            "direction": "up",
        },
    )


def remove_valuation_formula(card: dict[str, Any]) -> None:
    valuation = section(card, "valuation-a")
    valuation["blocks"] = [
        block for block in valuation["blocks"] if block["type"] != "formula"
    ]


def range_position_block(card: dict[str, Any]) -> dict[str, Any]:
    return next(
        block
        for block in section(card, "valuation-a")["blocks"]
        if block["type"] == "range_position"
    )


def test_schema_is_valid(schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)


def test_v1_2_example_satisfies_schema(
    validator: Draft202012Validator,
    example: dict[str, Any],
) -> None:
    validator.validate(example)


def test_v1_2_example_passes_backend_contract(example: dict[str, Any]) -> None:
    quality_grid = section(example, "quality")["blocks"][0]
    table = next(
        block
        for column in quality_grid["columns"]
        for block in column
        if block["type"] == "table"
    )
    assert [column["key"] for column in table["columns"]] == [
        "value",
        "assessment",
    ]
    cycle_block = lifecycle_block(example)
    assert cycle_block["stage"] == example["cycle_stage"]
    assert section(example, "cycle")["blocks"][0]["type"] == "industry_lifecycle"
    assert all(
        block["type"] != "industry_cycle"
        for block in section(example, "cycle")["blocks"]
    )
    assert all(
        block["type"] != "formula"
        for section_id in (
            "quality",
            "cycle",
            "position-a",
            "expected-return-a",
        )
        for block in section(example, section_id)["blocks"]
    )
    assert any(
        block["type"] == "formula"
        for block in section(example, "valuation-a")["blocks"]
    )
    validate_card(copy.deepcopy(example))


def test_contract_fixture_matrix(
    validator: Draft202012Validator,
    example: dict[str, Any],
) -> None:
    stable = single_market_card(
        example,
        path="stable",
        asset_type="stock",
        module="dividend_yield",
    )
    cyclical = single_market_card(
        example,
        path="cyclical",
        asset_type="stock",
        module="normalized_earnings",
    )
    model_table = next(
        block
        for block in section(cyclical, "model-pev-a")["blocks"]
        if block["type"] == "table"
    )
    model_table["rows"][0]["note"] = (
        "这是一段用于验证长文本排版压力测试的说明，覆盖行业景气、价格传导、"
        "库存周期、资本开支与估值回归之间的复杂关系。"
    )
    etf = single_market_card(
        example,
        path="etf",
        asset_type="etf",
        module="index_percentile",
        market="CN",
        code="510300",
    )
    add_etf_metrics(etf)

    for card in (example, stable, cyclical, etf):
        validator.validate(card)
        validate_v1_2_card(card)


def test_etf_aggregate_pb_rejects_arithmetic_mean(
    validator: Draft202012Validator,
    example: dict[str, Any],
) -> None:
    valid = single_market_card(
        example,
        path="etf",
        asset_type="etf",
        module="index_percentile",
        market="CN",
        code="510300",
    )
    arithmetic_pb, harmonic_pb = add_etf_metrics(valid)
    validator.validate(valid)
    validate_v1_2_card(valid)
    assert not SCORECARD.semantic_errors(valid)

    card = copy.deepcopy(valid)
    card["markets"][0]["valuation"]["pb"] = round(arithmetic_pb, 4)
    card["markets"][0]["etf_metrics"]["representative_pb"] = round(arithmetic_pb, 4)

    assert not list(validator.iter_errors(card))
    with pytest.raises(CardContractError, match="算术平均"):
        validate_v1_2_card(card)
    assert any(
        "算术平均" in error for error in SCORECARD.semantic_errors(card)
    )
    assert arithmetic_pb > harmonic_pb + 0.1


def test_etf_card_requires_metrics(
    validator: Draft202012Validator,
    example: dict[str, Any],
) -> None:
    card = single_market_card(
        example,
        path="etf",
        asset_type="etf",
        module="index_percentile",
        market="CN",
        code="510300",
    )
    errors = list(validator.iter_errors(card))
    assert errors
    assert any("etf_metrics" in error.message for error in errors)


def test_etf_top10_partial_coverage_is_supported(
    validator: Draft202012Validator,
    example: dict[str, Any],
) -> None:
    card = single_market_card(
        example,
        path="etf",
        asset_type="etf",
        module="index_percentile",
        market="CN",
        code="510300",
    )
    add_etf_metrics(card)
    metrics = card["markets"][0]["etf_metrics"]
    metrics["constituents"][3]["weight_pct"] = 8.0
    coverage = sum(item["weight_pct"] for item in metrics["constituents"])
    harmonic_pb = coverage / sum(
        item["weight_pct"] / item["pb"] for item in metrics["constituents"]
    )
    metrics["coverage_pct"] = coverage
    metrics["representative_pb"] = round(harmonic_pb, 4)
    card["markets"][0]["valuation"]["pb"] = round(harmonic_pb, 4)

    validator.validate(card)
    validate_v1_2_card(card)
    assert not SCORECARD.semantic_errors(card)
    assert coverage < 100


def test_etf_metrics_require_coverage_consistency(
    validator: Draft202012Validator,
    example: dict[str, Any],
) -> None:
    card = single_market_card(
        example,
        path="etf",
        asset_type="etf",
        module="index_percentile",
        market="CN",
        code="510300",
    )
    add_etf_metrics(card)
    card["markets"][0]["etf_metrics"]["constituents"][0]["weight_pct"] = 20.0

    assert not list(validator.iter_errors(card))
    with pytest.raises(CardContractError, match="coverage_pct"):
        validate_v1_2_card(card)
    assert any("coverage_pct" in error for error in SCORECARD.semantic_errors(card))


def test_etf_metrics_reject_nav_mismatch(
    validator: Draft202012Validator,
    example: dict[str, Any],
) -> None:
    card = single_market_card(
        example,
        path="etf",
        asset_type="etf",
        module="index_percentile",
        market="CN",
        code="510300",
    )
    add_etf_metrics(card)
    card["markets"][0]["etf_metrics"]["nav"] *= 0.9

    assert not list(validator.iter_errors(card))
    with pytest.raises(CardContractError, match="premium_discount_pct"):
        validate_v1_2_card(card)
    assert any(
        "premium_discount_pct" in error
        for error in SCORECARD.semantic_errors(card)
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda card: card["markets"][0]["expected_return"].__setitem__("total", 99),
        lambda card: card["presentation"]["sections"][4].__setitem__(
            "id", "dashboard-a"
        ),
        lambda card: section(card, "quality")["blocks"][0]["columns"][0][1][
            "items"
        ][0].__setitem__("label", "错误维度"),
        add_quality_dimension_column,
        lambda card: lifecycle_block(card).__setitem__("stage", "衰退期"),
        make_cyclical_without_cycle_chart,
        add_cycle_with_reversed_direction,
        remove_valuation_formula,
        lambda card: section(card, "dashboard-a")["blocks"][0]["items"][1].__setitem__(
            "key", "safety_margin"
        ),
        lambda card: section(card, "cross-market")["blocks"][2]["items"][0].__setitem__(
            "share_pct", 60
        ),
        lambda card: card["presentation"]["sections"].remove(
            section(card, "valuation-h")
        ),
        lambda card: range_position_block(card).__setitem__("fair_mid", 61),
        lambda card: section(card, "model-pev-a")["blocks"][1]["rows"][0].__setitem__(
            "unexpected", "value"
        ),
        lambda card: card["codes"].__setitem__("A", "000000.SH"),
        lambda card: card["markets"][0]["position"]["tranches"][0].__setitem__(
            "allocation_pct", 50
        ),
        lambda card: card["markets"][0]["position"]["tranches"][2].__setitem__(
            "trigger_type", "catalyst"
        ),
        lambda card: section(card, "dashboard-a")["blocks"][0]["items"][0].__setitem__(
            "value", 1
        ),
        lambda card: section(card, "dashboard-a")["blocks"][0]["items"][2].__setitem__(
            "kind", "yield_pct"
        ),
    ],
    ids=[
        "expected-return-not-closed",
        "duplicate-section-id",
        "quality-labels",
        "quality-redundant-dimension",
        "lifecycle-stage-not-synced",
        "cyclical-without-cycle-chart",
        "cycle-direction-inconsistent",
        "valuation-without-formula",
        "dashboard-gauge-keys",
        "premium-shares",
        "missing-market-section",
        "range-not-synced",
        "table-row-column-keys",
        "market-code-mismatch",
        "position-allocation-not-closed",
        "position-trigger-order",
        "dashboard-value-not-synced",
        "dashboard-gauge-kind",
    ],
)
def test_semantically_invalid_cards_are_rejected(
    validator: Draft202012Validator,
    example: dict[str, Any],
    mutate: Any,
) -> None:
    card = copy.deepcopy(example)
    mutate(card)

    assert not list(validator.iter_errors(card))
    with pytest.raises(CardContractError):
        validate_v1_2_card(card)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda card: card["presentation"]["sections"][0]["blocks"].append(
            {"type": "scenario_bars", "items": []}
        ),
        lambda card: section(card, "cycle")["blocks"].remove(
            lifecycle_block(card)
        ),
        lambda card: card["conclusion"].__setitem__(
            "confidence",
            {"code": "中", "label": "中"},
        ),
        lambda card: card["markets"][0].__setitem__("price", None),
        lambda card: card["markets"][0]["valuation"].__setitem__(
            "percentile", None
        ),
        lambda card: card["presentation"]["sections"][0].__setitem__(
            "role",
            "a-stock-dashboard",
        ),
        lambda card: section(card, "model-pev-a").pop("module"),
        lambda card: card["markets"][0]["expected_return"].pop("total"),
        lambda card: card["markets"][0]["position"]["tranches"][0].__setitem__(
            "allocation_pct",
            "40%",
        ),
        lambda card: card["model_modules"].append("index_percentile"),
        lambda card: card.__setitem__("path", "etf"),
        lambda card: section(card, "dashboard-a")["blocks"].append(
            {"type": "paragraph", "text": "dashboard must contain gauges only"}
        ),
        lambda card: section(card, "dashboard-a")["blocks"][0]["items"].pop(),
        lambda card: section(card, "valuation-a").__setitem__("title", "A 股估值"),
    ],
    ids=[
        "legacy-block",
        "cycle-position-missing",
        "localized-confidence-code",
        "null-price",
        "null-percentile",
        "unknown-section-role",
        "model-module-missing",
        "expected-return-not-closed",
        "percentage-as-string",
        "module-not-allowed-for-path",
        "etf-path-with-stock-asset",
        "dashboard-extra-block",
        "dashboard-three-gauges",
        "market-specific-section-title",
    ],
)
def test_invalid_cards_are_rejected(
    validator: Draft202012Validator,
    example: dict[str, Any],
    mutate: Any,
) -> None:
    card = copy.deepcopy(example)
    mutate(card)

    assert list(validator.iter_errors(card))
