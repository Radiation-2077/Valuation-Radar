#!/usr/bin/env python3
"""价值投资数据卡（data/*.json）的校验与盘点工具。

用法：
    scorecard.py validate <file.json> [<file.json> ...]
    scorecard.py list [--dir data]

validate 检查字段完整性、类型、数值范围与内部一致性（安全边际、合计年化）。
只做"能不能用"的结构校验，不判断投资结论对错。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_TOP = [
    "schema_version", "analysis_date", "name", "asset_type", "path",
    "quality", "markets",
]
VALID_PATHS = {"stable", "cyclical", "financial", "etf"}
VALID_ASSET = {"stock", "etf"}
REQUIRED_MARKET = [
    "market", "price", "fair_mid", "safety_margin_pct",
    "expected_return", "downside",
]
REQUIRED_ER = ["dividend", "growth", "valuation", "total"]
VALID_SCHEMA = {"1.0", "1.1"}
VALID_BLOCKS = {
    "heading", "paragraph", "callout", "table", "formula", "bullets",
    "scores", "quality_scorecard",
    "gauges", "valuation_scenarios", "range_position", "premium_donut",
    "position_tiers", "return_stack", "risk_cards", "grid", "metric_cards",
    "scenario_bars", "donut", "steps", "scale",
}
QUALITY_KEYS = {
    "profit_cash_quality", "balance_sheet", "roe", "moat", "survival",
}


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _validate_presentation(card: dict) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warn: list[str] = []
    presentation = card.get("presentation")
    if not isinstance(presentation, dict):
        return ["schema 1.1 缺 presentation 对象"], warn
    sections = presentation.get("sections")
    if not isinstance(sections, list) or not sections:
        return ["presentation.sections 必须是非空数组"], warn

    quality_cards: list[dict] = []
    section_ids: set[str] = set()
    for s_idx, section in enumerate(sections):
        tag = f"presentation.sections[{s_idx}]"
        if not isinstance(section, dict):
            errs.append(f"{tag} 不是对象")
            continue
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id:
            errs.append(f"{tag}.id 缺失")
        elif section_id in section_ids:
            errs.append(f"{tag}.id 重复：{section_id}")
        else:
            section_ids.add(section_id)
        if not isinstance(section.get("title"), str) or not section.get("title"):
            errs.append(f"{tag}.title 缺失")
        market = section.get("market")
        if market not in {"common", "A", "H", "US", "CN"}:
            errs.append(f"{tag}.market 非法：{market!r}")
        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errs.append(f"{tag}.blocks 必须是非空数组")
            continue
        for b_idx, block in enumerate(blocks):
            btag = f"{tag}.blocks[{b_idx}]"
            if not isinstance(block, dict):
                errs.append(f"{btag} 不是对象")
                continue
            block_type = block.get("type")
            if block_type not in VALID_BLOCKS:
                errs.append(f"{btag}.type 非法：{block_type!r}")
                continue
            if block_type == "quality_scorecard":
                quality_cards.append(block)
                dimensions = block.get("dimensions")
                if not isinstance(dimensions, list) or len(dimensions) != 5:
                    errs.append(f"{btag}.dimensions 必须恰好 5 项")
                    continue
                keys = [d.get("key") for d in dimensions if isinstance(d, dict)]
                if set(keys) != QUALITY_KEYS or len(set(keys)) != 5:
                    errs.append(f"{btag}.dimensions.key 必须是 {sorted(QUALITY_KEYS)}")
                scale_max = block.get("scale_max", 10)
                for d_idx, dimension in enumerate(dimensions):
                    dtag = f"{btag}.dimensions[{d_idx}]"
                    if not isinstance(dimension, dict):
                        errs.append(f"{dtag} 不是对象")
                        continue
                    for key in ("label", "indicator", "value", "assessment"):
                        if not isinstance(dimension.get(key), str) or not dimension.get(key):
                            errs.append(f"{dtag}.{key} 缺失")
                    score = dimension.get("score")
                    if not _is_num(score) or not 0 <= score <= float(scale_max):
                        errs.append(f"{dtag}.score 应为 0–{scale_max} 数值")
            elif block_type == "position_tiers":
                items = block.get("items")
                if not isinstance(items, list) or len(items) != 3:
                    errs.append(f"{btag}.items 必须是 3 档")
                else:
                    allocations = [i.get("allocation_pct") for i in items if isinstance(i, dict)]
                    if not all(_is_num(v) for v in allocations):
                        errs.append(f"{btag}.allocation_pct 必须为数值")
                    elif abs(sum(allocation for allocation in allocations if _is_num(allocation)) - 100) > 0.1:
                        errs.append(f"{btag} 三档 allocation_pct 必须合计 100")
                    if [i.get("level") for i in items] != [1, 2, 3]:
                        errs.append(f"{btag}.level 必须依次为 1/2/3")
            elif block_type == "valuation_scenarios":
                items = block.get("items")
                if not isinstance(items, list) or len(items) != 3:
                    errs.append(f"{btag}.items 必须是保守/中性/乐观 3 档")
            elif block_type == "range_position":
                order = ["min", "fair_low", "fair_mid", "fair_high", "max"]
                values = [block.get(key) for key in order]
                if not all(_is_num(v) for v in values) or values != sorted(values):
                    errs.append(f"{btag} 必须满足 min ≤ fair_low ≤ fair_mid ≤ fair_high ≤ max")
            elif block_type == "return_stack":
                items = block.get("items")
                if not isinstance(items, list) or not items:
                    errs.append(f"{btag}.items 不能为空")
                else:
                    values = [i.get("value_pct") for i in items if isinstance(i, dict)]
                    if not all(_is_num(v) for v in values):
                        errs.append(f"{btag}.items.value_pct 必须为数值")
                    elif _is_num(block.get("total_pct")) and abs(sum(values) - block["total_pct"]) > 0.6:
                        errs.append(f"{btag} 收益分项合计与 total_pct 不一致")
            elif block_type == "premium_donut":
                items = block.get("items")
                if not isinstance(items, list) or not items:
                    errs.append(f"{btag}.items 不能为空")
                else:
                    shares = [i.get("share_pct") for i in items if isinstance(i, dict)]
                    if not all(_is_num(v) for v in shares):
                        errs.append(f"{btag}.items.share_pct 必须为数值")
                    elif abs(sum(shares) - 100) > 0.2:
                        errs.append(f"{btag}.items.share_pct 必须合计 100")

        is_exempt = section_id in {"sources", "disclaimer"}
        has_summary = any(
            isinstance(block, dict)
            and block.get("type") == "callout"
            and block.get("summary") is True
            for block in blocks
        )
        if not is_exempt and not has_summary:
            errs.append(f"{tag} 缺少 summary=true 的本章小结")

    if len(quality_cards) != 1:
        errs.append(f"presentation 必须且只能包含 1 个 quality_scorecard，实际 {len(quality_cards)}")
    return errs, warn


def validate_file(path: Path) -> list[str]:
    errs: list[str] = []
    warn: list[str] = []
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"无法解析 JSON: {exc}"], []

    if not isinstance(card, dict):
        return ["顶层不是对象"], []

    for k in REQUIRED_TOP:
        if k not in card:
            errs.append(f"缺顶层字段 {k}")

    schema_version = card.get("schema_version")
    if schema_version not in VALID_SCHEMA:
        errs.append(f"schema_version 非法: {schema_version!r}（应为 1.0 或 1.1）")
    if schema_version == "1.0":
        warn.append("schema 1.0 是历史兼容格式，缺少 presentation；新卡必须使用 1.1")
    elif schema_version == "1.1":
        presentation_errs, presentation_warn = _validate_presentation(card)
        errs.extend(presentation_errs)
        warn.extend(presentation_warn)
    if card.get("asset_type") not in VALID_ASSET:
        errs.append(f"asset_type 非法: {card.get('asset_type')!r}")
    if card.get("path") not in VALID_PATHS:
        errs.append(f"path 非法: {card.get('path')!r}（应为 stable/cyclical/financial/etf）")

    q = card.get("quality") or {}
    if not isinstance(q, dict):
        errs.append("quality 不是对象")
    else:
        r = q.get("rating")
        if r is None:
            errs.append("quality.rating 缺失")
        elif not _is_num(r) or not (0 <= r <= 3):
            errs.append(f"quality.rating 应为 0–3，实际 {r!r}")
        if "gate_pass" not in q:
            warn.append("quality.gate_pass 缺失，排序时按 True 处理")
        sc = q.get("score")
        if sc is not None and (not _is_num(sc) or not (0 <= sc <= 100)):
            errs.append(f"quality.score 应为 0–100，实际 {sc!r}")

    codes = card.get("codes") or {}
    if not isinstance(codes, dict) or not codes:
        errs.append("codes 缺失或为空（至少给一个市场代码）")

    name = card.get("name")
    date = card.get("analysis_date")
    if name and date:
        expected = f"{name}_{date}.json"
        if path.name != expected:
            warn.append(f"文件名 {path.name!r} 与 {expected!r} 不一致（规范要求 标的名_日期.json）")

    markets = card.get("markets")
    if not isinstance(markets, list) or not markets:
        errs.append("markets 缺失或为空")
        return errs, warn

    for i, m in enumerate(markets):
        tag = f"markets[{i}]({m.get('market') if isinstance(m, dict) else '?'})"
        if not isinstance(m, dict):
            errs.append(f"{tag} 不是对象")
            continue
        for k in REQUIRED_MARKET:
            if k not in m:
                errs.append(f"{tag} 缺字段 {k}")

        price, mid = m.get("price"), m.get("fair_mid")
        sm = m.get("safety_margin_pct")
        if _is_num(price) and _is_num(mid) and mid:
            calc = (mid - price) / mid * 100
            if _is_num(sm) and abs(calc - sm) > 1.0:
                warn.append(
                    f"{tag} safety_margin_pct={sm} 与 (中枢−现价)/中枢={calc:.1f} 差超过 1pct，"
                    f"确认中枢口径是否用了正文中性值"
                )
        elif not _is_num(sm):
            errs.append(f"{tag} safety_margin_pct 非数值")

        lo, hi = m.get("fair_low"), m.get("fair_high")
        if _is_num(lo) and _is_num(hi) and lo > hi:
            errs.append(f"{tag} fair_low {lo} > fair_high {hi}")
        if _is_num(lo) and _is_num(mid) and not (lo - 1e-6 <= mid <= hi + 1e-6 if _is_num(hi) else True):
            warn.append(f"{tag} fair_mid={mid} 落在 [fair_low, fair_high] 之外")

        er = m.get("expected_return")
        if not isinstance(er, dict):
            errs.append(f"{tag} expected_return 不是对象")
        else:
            for k in REQUIRED_ER:
                if k not in er:
                    errs.append(f"{tag}.expected_return 缺 {k}")
                elif not _is_num(er.get(k)):
                    errs.append(f"{tag}.expected_return.{k} 非数值")
            parts = [er.get(k) for k in ("dividend", "growth", "valuation")]
            if all(_is_num(p) for p in parts) and _is_num(er.get("total")):
                s = sum(parts) + (er.get("fx") or 0)
                if abs(s - er["total"]) > 0.6:
                    warn.append(
                        f"{tag} 分项合计 {s:.2f} 与 total {er['total']} 差超过 0.6pct，"
                        f"请在 notes 说明闭合关系"
                    )

        dd = (m.get("downside") or {}).get("max_drawdown_pct")
        if dd is not None and _is_num(dd) and dd > 0:
            warn.append(f"{tag} max_drawdown_pct={dd} 为正，规范要求回撤用负数")

        v = m.get("valuation") or {}
        if isinstance(v, dict):
            pc = v.get("percentile")
            if pc is not None and (not _is_num(pc) or not (0 <= pc <= 100)):
                errs.append(f"{tag} valuation.percentile 应为 0–100 或 null，实际 {pc!r}")

    if not card.get("risks"):
        warn.append("risks 为空，建议至少写 3 条传导路径")

    return errs, warn


def cmd_validate(args: argparse.Namespace) -> int:
    rc = 0
    for p in args.files:
        path = Path(p)
        if not path.exists():
            print(f"[MISS] {p}: 文件不存在")
            rc = 2
            continue
        errs, warn = validate_file(path)
        status = "OK" if not errs else "FAIL"
        print(f"[{status}] {p}" + (f"  ({len(warn)} 项提示)" if warn else ""))
        for e in errs:
            print(f"   ✗ {e}")
        for w in warn:
            print(f"   ! {w}")
        if errs:
            rc = 1
    return rc


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.dir)
    files = sorted(root.glob("*.json")) if root.is_dir() else []
    if not files:
        print(f"{root}/ 下没有数据卡")
        return 1
    print(f"{root}/ 共 {len(files)} 张数据卡：")
    for f in files:
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"  {f.name}  解析失败: {exc}")
            continue
        mk = "/".join(m.get("market", "?") for m in card.get("markets", []))
        q = (card.get("quality") or {}).get("rating")
        miss = card.get("missing") or []
        extra = f"  缺:{','.join(miss)}" if miss else ""
        print(f"  {f.name}  [{card.get('asset_type')}/{card.get('path')}] 市场:{mk} 质地:{q}★{extra}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="价值投资数据卡校验工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="校验数据卡")
    v.add_argument("files", nargs="+")
    v.set_defaults(func=cmd_validate)

    l = sub.add_parser("list", help="盘点数据卡")
    l.add_argument("--dir", default="data")
    l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
