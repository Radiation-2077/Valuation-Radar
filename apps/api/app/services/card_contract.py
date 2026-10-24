from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    PROJECT_ROOT
    / ".codex"
    / "skills"
    / "value-investing"
    / "references"
    / "card-v1.2.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

QUALITY_LABELS = [
    "利润现金含量",
    "资产负债表",
    "ROE 水平",
    "护城河强度",
    "生存能力",
]
QUALITY_TABLE_COLUMNS = [
    ("value", "结果", "value"),
    ("assessment", "评价", "assessment"),
]
DASHBOARD_GAUGE_KEYS = [
    "safety_margin",
    "percentile",
    "dividend",
    "certainty",
]
DASHBOARD_GAUGE_KINDS = {
    "safety_margin": "safety_margin_pct",
    "percentile": "percentile",
    "dividend": "score_0_100",
    "certainty": "certainty",
}
ROLE_ORDER = {
    "dashboard": 0,
    "quality": 1,
    "cycle": 2,
    "model_analysis": 3,
    "cross_market": 4,
    "valuation": 5,
    "position": 6,
    "expected_return": 7,
    "risks": 8,
    "conclusion": 9,
    "sources": 10,
    "disclaimer": 11,
}
PER_MARKET_ROLES = {
    "dashboard",
    "valuation",
    "position",
    "expected_return",
    "risks",
    "conclusion",
}
COMMON_ROLES = {"quality", "cycle", "sources", "disclaimer"}
FORMULA_REQUIRED_ROLES = {
    "model_analysis",
    "valuation",
}
FORMULA_ALLOWED_ROLES = {
    "model_analysis",
    "cross_market",
    "valuation",
}
FORBIDDEN_CROSS_MARKET_BLOCKS = {
    "valuation_scenarios",
    "range_position",
    "position_tiers",
    "return_stack",
}
TRIGGER_ORDER = ["valuation", "evidence", "stabilization"]


class CardContractError(ValueError):
    pass


def validate_v1_2_card(card: dict[str, Any]) -> None:
    error = best_match(VALIDATOR.iter_errors(card))
    if error is not None:
        path = ".".join(str(item) for item in error.absolute_path)
        location = f"{path}: " if path else ""
        raise CardContractError(f"{location}{error.message}")

    issues: list[str] = []
    markets = card["markets"]
    market_names = [str(market["market"]) for market in markets]
    offered_markets = set(market_names)
    sections = card["presentation"]["sections"]
    sections_by_role: dict[tuple[str, str], list[dict[str, Any]]] = {}

    if len(market_names) != len(set(market_names)):
        issues.append("markets[].market 必须唯一")
    if set(card["codes"]) != offered_markets:
        issues.append("codes 的市场必须与 markets[].market 完全一致")
    market_codes = [str(market["code"]) for market in markets]
    if len(market_codes) != len(set(market_codes)):
        issues.append("markets[].code 必须唯一")
    for index, market in enumerate(markets):
        market_name = str(market["market"])
        if card["codes"].get(market_name) != market["code"]:
            issues.append(f"codes.{market_name} 必须与 markets[{index}].code 一致")

    section_ids: set[str] = set()
    last_order = -1
    for index, section in enumerate(sections):
        path = f"presentation.sections[{index}]"
        section_id = section["id"]
        role = section["role"]
        market = section["market"]
        if section_id in section_ids:
            issues.append(f"{path}.id 重复：{section_id}")
        section_ids.add(section_id)
        sections_by_role.setdefault((role, market), []).append(section)

        order = ROLE_ORDER[role]
        if order < last_order:
            issues.append(f"{path}.role 顺序不符合固定页面壳层")
        last_order = max(last_order, order)

        if role in PER_MARKET_ROLES and market not in offered_markets:
            issues.append(f"{path}.market 必须是已上市市场")
        if role in COMMON_ROLES and market != "common":
            issues.append(f"{path}.market 必须为 common")
        if role == "cross_market" and market != "common":
            issues.append(f"{path}.market 必须为 common")
        for block in _walk_blocks(section["blocks"]):
            block_market = block.get("market")
            if market in {"A", "H", "US", "CN"} and block_market not in {
                None,
                market,
            }:
                issues.append(f"{path} 混入 {block_market} 市场 block")
            if block["type"] == "table":
                issues.extend(_table_issues(block, path))

    if not {"A", "H"}.issubset(offered_markets):
        cross_sections = sections_by_role.get(("cross_market", "common"), [])
        if cross_sections:
            issues.append("单市场卡不得包含 cross_market")
    else:
        cross_sections = sections_by_role.get(("cross_market", "common"), [])
        if len(cross_sections) != 1:
            issues.append("A/H 卡必须包含且只能包含一个 cross_market section")
        else:
            issues.extend(_validate_cross_market(cross_sections[0]))

    for market in offered_markets:
        for role in PER_MARKET_ROLES:
            matches = sections_by_role.get((role, market), [])
            if len(matches) != 1:
                issues.append(f"{market} 市场 role={role} 必须恰好一个")
        for role in ("quality", "cycle"):
            if len(sections_by_role.get((role, "common"), [])) != 1:
                issues.append(f"必须恰好一个 common role={role}")

    for role in ("sources", "disclaimer"):
        if len(sections_by_role.get((role, "common"), [])) != 1:
            issues.append(f"必须恰好一个 common role={role}")

    model_sections = [
        section for section in sections if section["role"] == "model_analysis"
    ]
    model_section_names = {section["module"] for section in model_sections}
    if model_section_names != set(card["model_modules"]):
        issues.append("model_modules 必须与 model_analysis sections 的 module 完全一致")

    quality_grids = [
        block
        for section in sections
        for block in _walk_blocks(section["blocks"])
        if block["type"] == "grid" and _quality_grid_parts(block) is not None
    ]
    if len(quality_grids) != 1:
        issues.append("presentation 必须恰好包含一个质量 grid")
    else:
        issues.extend(_quality_grid_issues(quality_grids[0]))

    cycle_sections = [
        section for section in sections if section["role"] == "cycle"
    ]
    cycle_blocks = [
        block
        for cycle_section in cycle_sections
        for block in _walk_blocks(cycle_section["blocks"])
    ]
    lifecycle_blocks = [
        block for block in cycle_blocks if block["type"] == "industry_lifecycle"
    ]
    if len(lifecycle_blocks) != 1:
        issues.append("产业周期章节必须恰好包含一个 industry_lifecycle")
    elif lifecycle_blocks[0]["stage"] != card["cycle_stage"]:
        issues.append("industry_lifecycle.stage 必须与顶层 cycle_stage 一致")
    if cycle_sections and cycle_sections[0]["blocks"][0]["type"] != "industry_lifecycle":
        issues.append("industry_lifecycle 必须是产业周期章节的第一个 block")

    industry_cycle_blocks = [
        block for block in cycle_blocks if block["type"] == "industry_cycle"
    ]
    if card["path"] == "cyclical" and len(industry_cycle_blocks) != 1:
        issues.append("周期型标的必须恰好包含一个 industry_cycle")
    if len(industry_cycle_blocks) > 1:
        issues.append("industry_cycle 最多只能有一个")
    if industry_cycle_blocks:
        cycle_block = industry_cycle_blocks[0]
        if cycle_block["position"] != card["cycle_position"]:
            issues.append("industry_cycle.position 必须与顶层 cycle_position 一致")
        expected_phase, expected_direction = _expected_cycle_phase(
            cycle_block["position"]
        )
        if cycle_block["phase"] != expected_phase:
            issues.append(
                f"industry_cycle.phase 与位置不匹配，应为 {expected_phase}"
            )
        if cycle_block["direction"] != expected_direction:
            issues.append(
                f"industry_cycle.direction 与位置不匹配，应为 {expected_direction}"
            )

    for section in sections:
        has_formula = any(
            block["type"] == "formula"
            for block in _walk_blocks(section["blocks"])
        )
        if has_formula and section["role"] not in FORMULA_ALLOWED_ROLES:
            issues.append(
                f"{section['id']} 不应展示公式；简单算术不进入报告公式卡"
            )
        if section["role"] in FORMULA_REQUIRED_ROLES and not has_formula:
            issues.append(
                f"{section['id']} 是计算章节，必须包含带符号与取值依据的 formula"
            )
        if section["role"] in {
            "dashboard",
            "sources",
            "disclaimer",
        }:
            continue
        last_block = section["blocks"][-1]
        if not (
            last_block["type"] == "callout"
            and last_block.get("summary") is True
        ):
            issues.append(
                f"{section['id']} 最后一项必须是 summary=true 的 callout"
            )

    for section in sections:
        if section["role"] == "dashboard":
            issues.extend(_dashboard_issues(section))

    for index, market in enumerate(markets):
        issues.extend(_market_issues(card, market, index, sections))

    if issues:
        raise CardContractError("；".join(dict.fromkeys(issues)))


def _expected_cycle_phase(position: float) -> tuple[str, str]:
    if position < 25:
        return "recovery", "up"
    if position < 50:
        return "upswing", "up"
    if position < 75:
        return "pullback", "down"
    return "downswing", "down"


def _dashboard_issues(section: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    gauges = section["blocks"][0]["items"]
    keys = [item["key"] for item in gauges]
    if keys != DASHBOARD_GAUGE_KEYS:
        issues.append(
            f"{section['id']} 的仪表盘必须依次为 {', '.join(DASHBOARD_GAUGE_KEYS)}"
        )
    for item in gauges:
        expected_kind = DASHBOARD_GAUGE_KINDS.get(item["key"])
        if expected_kind is not None and item["kind"] != expected_kind:
            issues.append(
                f"{section['id']}.{item['key']}.kind 必须为 {expected_kind}"
            )
    return issues


def _quality_grid_issues(grid: dict[str, Any]) -> list[str]:
    parts = _quality_grid_parts(grid)
    if parts is None:
        return ["质量 grid 必须包含 scores 与 table"]
    scores, table = parts
    issues: list[str] = []
    labels = [item["label"] for item in scores["items"]]
    if labels != QUALITY_LABELS:
        issues.append("质量 grid 五个评分维度顺序或名称不正确")
    columns = [
        (column.get("key"), column.get("label"), column.get("role"))
        for column in table.get("columns", [])
    ]
    if columns != QUALITY_TABLE_COLUMNS:
        issues.append("质量 grid table 必须依次为结果、评价两列")
    if len(table["rows"]) != 5:
        issues.append("质量 grid table 必须恰好五行")
    return issues


def _quality_grid_parts(
    block: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    blocks = [
        item
        for column in block.get("columns", [])
        for item in column
        if isinstance(item, dict)
    ]
    scores = next((item for item in blocks if item["type"] == "scores"), None)
    table = next((item for item in blocks if item["type"] == "table"), None)
    return (scores, table) if scores is not None and table is not None else None


def _table_issues(block: dict[str, Any], path: str) -> list[str]:
    columns = block.get("columns", [])
    if not columns:
        return []
    expected = {column["key"] for column in columns}
    issues: list[str] = []
    for index, row in enumerate(block["rows"]):
        if set(row) != expected:
            issues.append(
                f"{path}.blocks.table.rows[{index}] 的键必须与 columns 完全一致"
            )
    return issues


def _validate_cross_market(section: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    blocks = _walk_blocks(section["blocks"])
    for block in blocks:
        if block["type"] in FORBIDDEN_CROSS_MARKET_BLOCKS:
            issues.append(f"{section['id']} 不得包含 {block['type']}")
    donuts = [block for block in blocks if block["type"] == "premium_donut"]
    if len(donuts) != 1:
        issues.append("cross_market 必须恰好包含一个 premium_donut")
        return issues
    donut = donuts[0]
    if set(donut["market_pair"]) != {"A", "H"}:
        issues.append("premium_donut.market_pair 必须为 A/H")
    shares = sum(item["share_pct"] for item in donut["items"])
    contributions = sum(
        item["contribution_pct"] for item in donut["items"]
    )
    if abs(shares - 100) > 0.2:
        issues.append("premium_donut.share_pct 必须合计 100")
    if abs(contributions - donut["total_premium_pct"]) > 0.3:
        issues.append("premium_donut 分项贡献必须与 total_premium_pct 闭合")
    return issues


def _market_issues(
    card: dict[str, Any],
    market: dict[str, Any],
    index: int,
    sections: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    market_name = market["market"]
    path = f"markets[{index}]"
    low = float(market["fair_low"])
    mid = float(market["fair_mid"])
    high = float(market["fair_high"])
    if not low <= mid <= high:
        issues.append(f"{path} 合理区间顺序错误")
    expected_margin = (mid - float(market["price"])) / mid * 100
    if abs(expected_margin - float(market["safety_margin_pct"])) > 0.2:
        issues.append(f"{path}.safety_margin_pct 与现价/中枢不一致")

    expected = market["expected_return"]
    expected_total = (
        expected["dividend"]
        + expected["growth"]
        + expected["valuation"]
        + expected["fx"]
    )
    if abs(expected_total - expected["total"]) > 0.2:
        issues.append(f"{path}.expected_return 分项与 total 不一致")

    tranches = market["position"]["tranches"]
    if [tier["level"] for tier in tranches] != [1, 2, 3, 4]:
        issues.append(f"{path}.position.tranches level 必须为 1/2/3/4")
    if abs(sum(tier["allocation_pct"] for tier in tranches) - 100) > 0.2:
        issues.append(f"{path}.position.tranches allocation_pct 必须合计 100")
    trigger_types = [tier["trigger_type"] for tier in tranches]
    if trigger_types[:3] != TRIGGER_ORDER:
        issues.append(
            f"{path}.position.tranches 前三档必须依次为 valuation/evidence/stabilization"
        )
    if len(trigger_types) == 4 and trigger_types[3] not in {"catalyst", "reserve"}:
        issues.append(f"{path}.position.tranches 第四档必须为 catalyst/reserve")
    market_sections = [
        section
        for section in sections
        if section["market"] == market_name
    ]
    valuation = _one_block(market_sections, "valuation", "valuation_scenarios")
    range_position = _one_block(market_sections, "valuation", "range_position")
    position = _one_block(market_sections, "position", "position_tiers")
    returns = _one_block(market_sections, "expected_return", "return_stack")
    dashboard = _one_section(market_sections, "dashboard")

    if valuation is None:
        issues.append(f"{market_name} 缺少 valuation_scenarios")
    else:
        if valuation["currency"] != market["currency"]:
            issues.append(f"{market_name} valuation_scenarios currency 不一致")
        if abs(valuation["current_price"] - market["price"]) > 0.01:
            issues.append(f"{market_name} valuation_scenarios current_price 不一致")

    if range_position is None:
        issues.append(f"{market_name} 缺少 range_position")
    else:
        for key in ("fair_low", "fair_mid", "fair_high"):
            if abs(range_position[key] - market[key]) > 0.01:
                issues.append(f"{market_name} range_position.{key} 不一致")
        if abs(range_position["current_price"] - market["price"]) > 0.01:
            issues.append(f"{market_name} range_position current_price 不一致")

    if position is None:
        issues.append(f"{market_name} 缺少 position_tiers")
    else:
        if position["items"] != tranches:
            issues.append(f"{market_name} position_tiers 档位与 markets[].position.tranches 不一致")

    if returns is None:
        issues.append(f"{market_name} 缺少 return_stack")
    else:
        if abs(returns["total_pct"] - expected["total"]) > 0.2:
            issues.append(f"{market_name} return_stack.total_pct 不一致")
        by_source = {item["source"]: item["value_pct"] for item in returns["items"]}
        if set(by_source) != {"dividend", "growth", "valuation", "fx"}:
            issues.append(f"{market_name} return_stack source 必须完整")
        else:
            for source in ("dividend", "growth", "valuation", "fx"):
                if abs(by_source[source] - expected[source]) > 0.1:
                    issues.append(f"{market_name} return_stack {source} 不一致")

    if dashboard is None:
        issues.append(f"{market_name} 缺少 dashboard")
    else:
        gauges = {
            item["key"]: item
            for item in dashboard["blocks"][0]["items"]
        }
        safety_gauge = gauges.get("safety_margin")
        safety = safety_gauge["value"] if safety_gauge is not None else None
        if safety is None or abs(safety - market["safety_margin_pct"]) > 0.1:
            issues.append(f"{market_name} 仪表盘安全边际与 markets[] 不一致")
        percentile_gauge = gauges.get("percentile")
        percentile = (
            percentile_gauge["value"] if percentile_gauge is not None else None
        )
        market_percentile = market["valuation"]["percentile"]
        if percentile != market_percentile:
            issues.append(f"{market_name} 仪表盘估值分位与 markets[] 不一致")
        certainty_gauge = gauges.get("certainty")
        certainty = certainty_gauge["value"] if certainty_gauge is not None else None
        if certainty is None or abs(certainty - market["certainty"]) > 0.1:
            issues.append(f"{market_name} 仪表盘确定性与 markets[] 不一致")
    return issues


def _one_block(
    sections: list[dict[str, Any]],
    role: str,
    block_type: str,
) -> dict[str, Any] | None:
    matches = [
        block
        for section in sections
        if section["role"] == role
        for block in _walk_blocks(section["blocks"])
        if block["type"] == block_type
    ]
    return matches[0] if len(matches) == 1 else None


def _one_section(
    sections: list[dict[str, Any]],
    role: str,
) -> dict[str, Any] | None:
    matches = [section for section in sections if section["role"] == role]
    return matches[0] if len(matches) == 1 else None


def _walk_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for block in blocks:
        output.append(block)
        if block["type"] == "grid":
            for column in block["columns"]:
                output.extend(_walk_blocks(column))
    return output
