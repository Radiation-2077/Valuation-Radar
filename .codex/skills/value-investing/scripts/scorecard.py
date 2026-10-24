#!/usr/bin/env python3
"""Validate and inventory value-investing schema 1.2 cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SKILL_ROOT / "references" / "card-v1.2.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

QUALITY_LABELS = [
    "利润现金含量",
    "资产负债表",
    "ROE 水平",
    "护城河强度",
    "生存能力",
]
DASHBOARD_KEYS = ["safety_margin", "percentile", "dividend", "certainty"]
DASHBOARD_KINDS = {
    "safety_margin": "safety_margin_pct",
    "percentile": "percentile",
    "dividend": "score_0_100",
    "certainty": "certainty",
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
TRIGGER_ORDER = ["valuation", "evidence", "stabilization"]


def walk_blocks(blocks: list[dict]) -> list[dict]:
    output: list[dict] = []
    for block in blocks:
        output.append(block)
        if block["type"] == "grid":
            for column in block["columns"]:
                output.extend(walk_blocks(column))
    return output


def one_block(
    sections: list[dict],
    role: str,
    block_type: str,
) -> dict | None:
    matches = [
        block
        for section in sections
        if section["role"] == role
        for block in walk_blocks(section["blocks"])
        if block["type"] == block_type
    ]
    return matches[0] if len(matches) == 1 else None


def quality_parts(block: dict) -> tuple[dict, dict] | None:
    nested = [
        item
        for column in block["columns"]
        for item in column
    ]
    scores = next((item for item in nested if item["type"] == "scores"), None)
    table = next((item for item in nested if item["type"] == "table"), None)
    return (scores, table) if scores and table else None


def semantic_errors(card: dict) -> list[str]:
    errors: list[str] = []
    markets = card["markets"]
    market_names = [market["market"] for market in markets]
    offered = set(market_names)
    sections = card["presentation"]["sections"]

    if len(market_names) != len(set(market_names)):
        errors.append("markets[].market 必须唯一")
    if set(card["codes"]) != offered:
        errors.append("codes 市场必须与 markets[] 完全一致")
    for market in markets:
        if card["codes"].get(market["market"]) != market["code"]:
            errors.append(f"codes.{market['market']} 与 markets[].code 不一致")

    ids: set[str] = set()
    last_order = -1
    grouped: dict[tuple[str, str], list[dict]] = {}
    for index, section in enumerate(sections):
        tag = f"presentation.sections[{index}]"
        if section["id"] in ids:
            errors.append(f"{tag}.id 重复：{section['id']}")
        ids.add(section["id"])
        grouped.setdefault((section["role"], section["market"]), []).append(section)
        order = ROLE_ORDER[section["role"]]
        if order < last_order:
            errors.append(f"{tag}.role 顺序错误")
        last_order = max(last_order, order)
        if section["role"] in COMMON_ROLES and section["market"] != "common":
            errors.append(f"{tag}.market 必须为 common")
        if section["role"] == "cross_market" and section["market"] != "common":
            errors.append(f"{tag}.market 必须为 common")
        for block in walk_blocks(section["blocks"]):
            if (
                section["market"] in {"A", "H", "US", "CN"}
                and block.get("market") not in {None, section["market"]}
            ):
                errors.append(f"{tag} 混入其他市场 block")
            if block["type"] == "table" and block["columns"]:
                keys = {column["key"] for column in block["columns"]}
                for row_index, row in enumerate(block["rows"]):
                    if set(row) != keys:
                        errors.append(
                            f"{tag}.table.rows[{row_index}] 与 columns 键不一致"
                        )

    for market in offered:
        for role in PER_MARKET_ROLES:
            if len(grouped.get((role, market), [])) != 1:
                errors.append(f"{market} 市场 role={role} 必须恰好一个")
        for role in ("quality", "cycle"):
            if len(grouped.get((role, "common"), [])) != 1:
                errors.append(f"必须恰好一个 common role={role}")
    for role in ("sources", "disclaimer"):
        if len(grouped.get((role, "common"), [])) != 1:
            errors.append(f"必须恰好一个 common role={role}")

    if {"A", "H"}.issubset(offered):
        cross = grouped.get(("cross_market", "common"), [])
        if len(cross) != 1:
            errors.append("A/H 卡必须恰好一个 cross_market")
        else:
            errors.extend(cross_errors(cross[0]))
    elif grouped.get(("cross_market", "common")):
        errors.append("单市场卡不得包含 cross_market")

    modules = {
        section["module"]
        for section in sections
        if section["role"] == "model_analysis"
    }
    if modules != set(card["model_modules"]):
        errors.append("model_modules 与 model_analysis sections 不一致")

    grids = [
        block
        for section in sections
        for block in walk_blocks(section["blocks"])
        if block["type"] == "grid" and quality_parts(block)
    ]
    if len(grids) != 1:
        errors.append("必须恰好一个质量 grid")
    else:
        scores, table = quality_parts(grids[0]) or ({}, {})
        if [item["label"] for item in scores["items"]] != QUALITY_LABELS:
            errors.append("质量 grid 五个维度顺序或名称错误")
        columns = [
            (column.get("key"), column.get("label"), column.get("role"))
            for column in table.get("columns", [])
        ]
        if columns != [
            ("value", "结果", "value"),
            ("assessment", "评价", "assessment"),
        ]:
            errors.append("质量 grid table 必须依次为结果、评价两列")
        if len(table["rows"]) != 5:
            errors.append("质量 grid 表格必须五行")

    cycle_sections = [
        section for section in sections if section["role"] == "cycle"
    ]
    cycle_blocks = [
        block
        for cycle_section in cycle_sections
        for block in walk_blocks(cycle_section["blocks"])
    ]
    lifecycle_blocks = [
        block for block in cycle_blocks if block["type"] == "industry_lifecycle"
    ]
    if len(lifecycle_blocks) != 1:
        errors.append("产业周期章节必须恰好包含一个 industry_lifecycle")
    elif lifecycle_blocks[0]["stage"] != card["cycle_stage"]:
        errors.append("industry_lifecycle.stage 必须与顶层 cycle_stage 一致")
    if cycle_sections and cycle_sections[0]["blocks"][0]["type"] != "industry_lifecycle":
        errors.append("industry_lifecycle 必须是产业周期章节的第一个 block")

    industry_cycle_blocks = [
        block for block in cycle_blocks if block["type"] == "industry_cycle"
    ]
    if card["path"] == "cyclical" and len(industry_cycle_blocks) != 1:
        errors.append("周期型标的必须恰好包含一个 industry_cycle")
    if len(industry_cycle_blocks) > 1:
        errors.append("industry_cycle 最多只能有一个")
    if industry_cycle_blocks:
        cycle_block = industry_cycle_blocks[0]
        if cycle_block["position"] != card["cycle_position"]:
            errors.append("industry_cycle.position 必须与顶层 cycle_position 一致")
        expected_phase, expected_direction = expected_cycle_phase(
            cycle_block["position"]
        )
        if cycle_block["phase"] != expected_phase:
            errors.append(
                f"industry_cycle.phase 与位置不匹配，应为 {expected_phase}"
            )
        if cycle_block["direction"] != expected_direction:
            errors.append(
                f"industry_cycle.direction 与位置不匹配，应为 {expected_direction}"
            )

    for section in sections:
        has_formula = any(
            block["type"] == "formula"
            for block in walk_blocks(section["blocks"])
        )
        if has_formula and section["role"] not in FORMULA_ALLOWED_ROLES:
            errors.append(
                f"{section['id']} 不应展示公式；简单算术不进入报告公式卡"
            )
        if section["role"] in FORMULA_REQUIRED_ROLES and not has_formula:
            errors.append(
                f"{section['id']} 是计算章节，必须包含带符号与取值依据的 formula"
            )
        if section["role"] in {"dashboard", "sources", "disclaimer"}:
            continue
        last = section["blocks"][-1]
        if not (last["type"] == "callout" and last.get("summary") is True):
            errors.append(f"{section['id']} 最后一项必须是 summary callout")
        if section["role"] == "dashboard":
            pass
    for section in sections:
        if section["role"] == "dashboard":
            errors.extend(dashboard_errors(section))

    for market in markets:
        errors.extend(market_errors(card, market, sections))
    return errors


def expected_cycle_phase(position: float) -> tuple[str, str]:
    if position < 25:
        return "recovery", "up"
    if position < 50:
        return "upswing", "up"
    if position < 75:
        return "pullback", "down"
    return "downswing", "down"


def dashboard_errors(section: dict) -> list[str]:
    items = section["blocks"][0]["items"]
    errors: list[str] = []
    if [item["key"] for item in items] != DASHBOARD_KEYS:
        errors.append(f"{section['id']} 必须固定四项仪表盘")
    for item in items:
        expected = DASHBOARD_KINDS.get(item["key"])
        if expected and item["kind"] != expected:
            errors.append(f"{section['id']}.{item['key']}.kind 必须为 {expected}")
    return errors


def cross_errors(section: dict) -> list[str]:
    blocks = walk_blocks(section["blocks"])
    errors: list[str] = []
    forbidden = {
        "valuation_scenarios",
        "range_position",
        "position_tiers",
        "return_stack",
    }
    errors.extend(
        f"cross_market 不得包含 {block['type']}"
        for block in blocks
        if block["type"] in forbidden
    )
    donuts = [block for block in blocks if block["type"] == "premium_donut"]
    if len(donuts) != 1:
        errors.append("cross_market 必须恰好一个 premium_donut")
        return errors
    donut = donuts[0]
    if set(donut["market_pair"]) != {"A", "H"}:
        errors.append("premium_donut.market_pair 必须为 A/H")
    if abs(sum(item["share_pct"] for item in donut["items"]) - 100) > 0.2:
        errors.append("premium_donut.share_pct 必须合计 100")
    if (
        abs(
            sum(item["contribution_pct"] for item in donut["items"])
            - donut["total_premium_pct"]
        )
        > 0.3
    ):
        errors.append("premium_donut 分项贡献必须与 total 闭合")
    return errors


def market_errors(card: dict, market: dict, sections: list[dict]) -> list[str]:
    name = market["market"]
    sections = [section for section in sections if section["market"] == name]
    errors: list[str] = []
    if card["path"] == "etf":
        errors.extend(etf_metrics_errors(market))
    elif market.get("etf_metrics") is not None:
        errors.append(f"{name} 仅 ETF 可以包含 etf_metrics")
    expected = market["expected_return"]
    if (
        abs(
            expected["dividend"]
            + expected["growth"]
            + expected["valuation"]
            + expected["fx"]
            - expected["total"]
        )
        > 0.2
    ):
        errors.append(f"{name} expected_return 分项与 total 不一致")
    margin = (
        (market["fair_mid"] - market["price"]) / market["fair_mid"] * 100
    )
    if abs(margin - market["safety_margin_pct"]) > 0.2:
        errors.append(f"{name} safety_margin_pct 不一致")
    tranches = market["position"]["tranches"]
    if [item["level"] for item in tranches] != [1, 2, 3, 4]:
        errors.append(f"{name} position tranches level 必须为 1/2/3/4")
    if abs(sum(item["allocation_pct"] for item in tranches) - 100) > 0.2:
        errors.append(f"{name} position tranches 必须合计 100")
    trigger_types = [item["trigger_type"] for item in tranches]
    if trigger_types[:3] != TRIGGER_ORDER:
        errors.append(
            f"{name} 前三档必须依次为 valuation/evidence/stabilization"
        )
    if len(trigger_types) == 4 and trigger_types[3] not in {"catalyst", "reserve"}:
        errors.append(f"{name} 第四档必须为 catalyst/reserve")

    scenarios = one_block(sections, "valuation", "valuation_scenarios")
    range_position = one_block(sections, "valuation", "range_position")
    position = one_block(sections, "position", "position_tiers")
    returns = one_block(sections, "expected_return", "return_stack")
    dashboard = next(
        (section for section in sections if section["role"] == "dashboard"),
        None,
    )
    if scenarios is None:
        errors.append(f"{name} 缺少 valuation_scenarios")
    else:
        if abs(scenarios["current_price"] - market["price"]) > 0.01:
            errors.append(f"{name} valuation_scenarios 现价不一致")
    if range_position is None:
        errors.append(f"{name} 缺少 range_position")
    else:
        for key in ("fair_low", "fair_mid", "fair_high"):
            if abs(range_position[key] - market[key]) > 0.01:
                errors.append(f"{name} range_position.{key} 不一致")
    if position is None:
        errors.append(f"{name} 缺少 position_tiers")
    else:
        if position["items"] != tranches:
            errors.append(f"{name} position tiers 不一致")
    if returns is None:
        errors.append(f"{name} 缺少 return_stack")
    else:
        if abs(returns["total_pct"] - expected["total"]) > 0.2:
            errors.append(f"{name} return total 不一致")
        values = {item["source"]: item["value_pct"] for item in returns["items"]}
        for source in ("dividend", "growth", "valuation", "fx"):
            if abs(values.get(source, 999) - expected[source]) > 0.1:
                errors.append(f"{name} return_stack.{source} 不一致")
    if dashboard is None:
        errors.append(f"{name} 缺少 dashboard")
    else:
        gauges = {item["key"]: item for item in dashboard["blocks"][0]["items"]}
        if gauges.get("safety_margin", {}).get("value") != market["safety_margin_pct"]:
            errors.append(f"{name} 仪表盘安全边际不一致")
        if gauges.get("percentile", {}).get("value") != market["valuation"]["percentile"]:
            errors.append(f"{name} 仪表盘估值分位不一致")
        if gauges.get("certainty", {}).get("value") != market["certainty"]:
            errors.append(f"{name} 仪表盘确定性不一致")
    return errors


def etf_metrics_errors(market: dict) -> list[str]:
    name = market["market"]
    metrics = market.get("etf_metrics")
    if not isinstance(metrics, dict):
        return [f"{name} ETF 缺少 etf_metrics"]

    errors: list[str] = []
    constituents = metrics["constituents"]
    weight_sum = sum(item["weight_pct"] for item in constituents)
    if abs(weight_sum - float(metrics["coverage_pct"])) > 0.1:
        errors.append(
            f"{name} ETF 前十大成分权重合计必须等于 coverage_pct"
        )

    representative_pb = float(metrics["representative_pb"])
    if abs(representative_pb - float(market["valuation"]["pb"])) > 0.02:
        errors.append(
            f"{name} valuation.pb 必须等于 etf_metrics.representative_pb"
        )

    harmonic_pb = weight_sum / sum(
        item["weight_pct"] / item["pb"] for item in constituents
    )
    weighted_pb_sum = sum(
        item["weight_pct"] * item["pb"] for item in constituents
    )
    arithmetic_candidates = {
        round(weighted_pb_sum / weight_sum, 6),
        round(weighted_pb_sum / 100, 6),
    }
    tolerance = max(0.01, harmonic_pb * 0.01)
    if abs(representative_pb - harmonic_pb) > tolerance:
        arithmetic_pb = min(
            arithmetic_candidates,
            key=lambda value: abs(representative_pb - value),
        )
        if abs(representative_pb - arithmetic_pb) <= tolerance:
            errors.append(
                f"{name} ETF 前十大代表 PB 使用了算术平均 {arithmetic_pb:.3f}；"
                f"归一化市值权重必须使用调和平均 {harmonic_pb:.3f}"
            )
        else:
            errors.append(
                f"{name} ETF 前十大代表 PB 与成分复算不一致："
                f"填报 {representative_pb:.3f}，调和平均 {harmonic_pb:.3f}"
            )

    if metrics["pb_as_of"] != market["price_date"]:
        errors.append(f"{name} etf_metrics.pb_as_of 必须等于 price_date")
    if metrics["nav_date"] != market["price_date"]:
        errors.append(f"{name} etf_metrics.nav_date 必须等于 price_date")
    expected_premium = (
        float(market["price"]) / float(metrics["nav"]) - 1
    ) * 100
    if abs(expected_premium - float(metrics["premium_discount_pct"])) > 0.05:
        errors.append(
            f"{name} etf_metrics.premium_discount_pct 与 price/nav 不一致"
        )
    return errors


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"无法解析 JSON: {exc}"], warnings
    if not isinstance(card, dict):
        return ["顶层不是对象"], warnings
    schema_error = best_match(VALIDATOR.iter_errors(card))
    if schema_error is not None:
        location = ".".join(str(item) for item in schema_error.absolute_path)
        prefix = f"{location}: " if location else ""
        return [f"schema 1.2 校验失败：{prefix}{schema_error.message}"], warnings
    expected_name = f"{card['name']}_{card['analysis_date']}.json"
    if path.name != expected_name:
        warnings.append(f"文件名应为 {expected_name}")
    return semantic_errors(card), warnings


def cmd_validate(args: argparse.Namespace) -> int:
    rc = 0
    for value in args.files:
        path = Path(value)
        if not path.exists():
            print(f"[MISS] {path}: 文件不存在")
            rc = 2
            continue
        errors, warnings = validate_file(path)
        print(f"[{'OK' if not errors else 'FAIL'}] {path}")
        for error in errors:
            print(f"   ✗ {error}")
        for warning in warnings:
            print(f"   ! {warning}")
        if errors:
            rc = 1
    return rc


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.dir)
    files = sorted(root.glob("*.json")) if root.is_dir() else []
    if not files:
        print(f"{root}/ 下没有数据卡")
        return 1
    print(f"{root}/ 共 {len(files)} 张数据卡：")
    for path in files:
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"  {path.name}  解析失败: {exc}")
            continue
        markets = "/".join(
            str(market.get("market", "?")) for market in card.get("markets", [])
        )
        quality = (card.get("quality") or {}).get("rating")
        print(
            f"  {path.name}  "
            f"[schema {card.get('schema_version')}/{card.get('asset_type')}/"
            f"{card.get('path')}] 市场:{markets} 质地:{quality}★"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate value-investing schema 1.2 cards")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("files", nargs="+")
    validate.set_defaults(func=cmd_validate)
    listing = subparsers.add_parser("list")
    listing.add_argument("--dir", default="data")
    listing.set_defaults(func=cmd_list)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
