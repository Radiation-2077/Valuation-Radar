#!/usr/bin/env python3
"""把 value-investing 数据卡转换为三套风险偏好的结构化排序 JSON。"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import itertools
import json
import sys
from pathlib import Path

PROFILES = {
    "conservative": {
        "label": "稳健保守",
        "description": "风险与确定性优先",
        "weights": {"margin": 0.25, "base": 0.15, "risk": 0.30, "stability": 0.30},
    },
    "balanced": {
        "label": "均衡",
        "description": "默认基准",
        "weights": {"margin": 0.30, "base": 0.25, "risk": 0.20, "stability": 0.25},
    },
    "aggressive": {
        "label": "进取",
        "description": "以预期收益为主",
        "weights": {"margin": 0.25, "base": 0.40, "risk": 0.15, "stability": 0.20},
    },
}

ANCHOR_MARGIN = [
    (-30, 0), (-15, 10), (0, 42), (10, 60),
    (20, 76), (30, 87), (40, 95), (60, 100),
]
ANCHOR_EXCESS = [
    (-3, 8), (-1, 22), (0, 35), (2, 50), (4, 62),
    (6, 72), (8, 82), (12, 93), (18, 100),
]
ANCHOR_DD = [
    (10, 97), (16, 90), (22, 80), (26, 72), (31, 62),
    (36, 52), (42, 42), (50, 30), (60, 18),
]
VALUE_SCORECARD = (
    Path(__file__).resolve().parents[2]
    / "value-investing"
    / "scripts"
    / "scorecard.py"
)


def load_card_validator():
    spec = importlib.util.spec_from_file_location("value_scorecard", VALUE_SCORECARD)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 value-investing scorecard：{VALUE_SCORECARD}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_file


def lerp_anchor(value: float, anchors: list[tuple[float, float]]) -> float:
    if value <= anchors[0][0]:
        return float(anchors[0][1])
    if value >= anchors[-1][0]:
        return float(anchors[-1][1])
    for (x0, y0), (x1, y1) in itertools.pairwise(anchors):
        if x0 <= value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return float(anchors[-1][1])


def num(value, default=None):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def label_of(value, default=""):
    if isinstance(value, str):
        return value or default
    if isinstance(value, dict):
        return str(value.get("label") or value.get("code") or default)
    return default


def confidence_code(value):
    if isinstance(value, dict):
        return str(value.get("code") or "")
    return "low" if value == "低" else ""


def band_of(score: float) -> str:
    if score >= 75:
        return "S"
    if score >= 65:
        return "A"
    if score >= 55:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def rf_for(card: dict, market: dict) -> float:
    macro = card.get("macro") or {}
    if str(market.get("currency") or "CNY").upper() == "CNY":
        return num(macro.get("rf_cny"), 1.7)
    return num(macro.get("rf_usd"), num(macro.get("rf_cny"), 4.5))


def days_since(value: str, today: dt.date) -> int | None:
    try:
        return max(0, (today - dt.date.fromisoformat(value)).days)
    except (TypeError, ValueError):
        return None


def build_entries(cards: list[dict], today: dt.date) -> list[dict]:
    entries: list[dict] = []
    for card in cards:
        quality = card.get("quality") or {}
        conclusion = card.get("conclusion") or {}
        rating = num(quality.get("rating"), 0)
        quality_score = num(quality.get("score"), 60)
        path = str(card.get("path") or "stable")
        asset_type = str(card.get("asset_type") or "stock")
        cycle_position = num(card.get("cycle_position"))

        for market in card.get("markets") or []:
            expected = market.get("expected_return") or {}
            downside = market.get("downside") or {}
            valuation = market.get("valuation") or {}
            safety_margin = num(market.get("safety_margin_pct"))
            total_return = num(expected.get("total"))
            dividend = num(expected.get("dividend"), 0)
            growth = num(expected.get("growth"), 0)
            fx = num(expected.get("fx"), 0)
            valuation_return = num(expected.get("valuation"), 0)
            drawdown = num(downside.get("max_drawdown_pct"))
            risk_free = rf_for(card, market)
            certainty = num(market.get("certainty"), quality_score)

            base_income = dividend + growth + fx
            score_margin = lerp_anchor(safety_margin, ANCHOR_MARGIN) if safety_margin is not None else None
            score_base = lerp_anchor(base_income - risk_free, ANCHOR_EXCESS)
            score_risk = lerp_anchor(abs(drawdown), ANCHOR_DD) if drawdown is not None else None
            if score_risk is not None and cycle_position is not None:
                score_risk = max(0.0, min(100.0, score_risk - (cycle_position - 50) / 50 * 8))
            score_stability = 0.55 * quality_score + 0.45 * certainty
            if path == "cyclical":
                score_stability -= 6
            if asset_type == "etf":
                score_stability -= 4
            if rating <= 1:
                score_stability *= 0.5
            if confidence_code(conclusion.get("confidence")) == "low":
                score_stability -= 5
            score_stability = max(0.0, min(100.0, score_stability))

            reasons: list[str] = []
            if not bool(quality.get("gate_pass", True)):
                reasons.append(str(quality.get("gate_reason") or "未通过质地门槛"))
            if rating < 2:
                reasons.append(f"质地 {rating}★ 不达标")
            entry = {
                "name": str(card.get("name") or "?"),
                "market": str(market.get("market") or "—"),
                "code": str(market.get("code") or ""),
                "currency": str(market.get("currency") or "CNY"),
                "asset_type": asset_type,
                "path": path,
                "industry": str(card.get("industry") or ""),
                "analysis_date": str(card.get("analysis_date") or ""),
                "stale_days": days_since(str(card.get("analysis_date") or ""), today),
                "quality_rating": rating,
                "quality_score": quality_score,
                "cycle_position": cycle_position,
                "price": num(market.get("price")),
                "fair_mid": num(market.get("fair_mid")),
                "safety_margin_pct": safety_margin,
                "expected_return_pct": total_return,
                "base_income_pct": base_income,
                "max_drawdown_pct": drawdown,
                "verdict": label_of(market.get("verdict") or conclusion.get("verdict")),
                "thesis": str(conclusion.get("thesis") or ""),
                "confidence": label_of(conclusion.get("confidence"), "中"),
                "pe": num(valuation.get("pe")),
                "pb": num(valuation.get("pb")),
                "percentile": num(valuation.get("percentile")),
                "risk_free_rate_pct": risk_free,
                "scores": {
                    "safety_margin": score_margin,
                    "base_income": score_base,
                    "downside": score_risk,
                    "stability": score_stability,
                },
                "excluded_reasons": reasons,
            }
            entry["risk_adjusted_ratio"] = (
                (total_return - risk_free) / abs(drawdown)
                if total_return is not None and drawdown else None
            )
            entry["valuation_reliance"] = (
                abs(valuation_return) / abs(total_return)
                if total_return and abs(total_return) > 0.01 else 0.0
            )
            flags = list(card.get("risks") or [])
            if entry["valuation_reliance"] > 0.4:
                flags.append("收益依赖估值回归")
            if rating <= 2:
                flags.append("质地带瑕疵")
            if (cycle_position or 0) >= 70:
                flags.append("周期高位")
            if confidence_code(conclusion.get("confidence")) == "low":
                flags.append("置信度低")
            entry["risk_flags"] = flags

            for code, profile in PROFILES.items():
                weights = profile["weights"]
                if any(entry["scores"][key] is None for key in ("safety_margin", "base_income", "downside")):
                    entry[f"score::{code}"] = None
                else:
                    entry[f"score::{code}"] = (
                        weights["margin"] * entry["scores"]["safety_margin"]
                        + weights["base"] * entry["scores"]["base_income"]
                        + weights["risk"] * entry["scores"]["downside"]
                        + weights["stability"] * entry["scores"]["stability"]
                    )
            entries.append(entry)
    return entries


def rounded(value, digits=1):
    return round(value, digits) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def serialize_entry(entry: dict, profile_code: str, rank: int | None = None) -> dict:
    score = entry.get(f"score::{profile_code}")
    payload = {
        key: value
        for key, value in entry.items()
        if not key.startswith("score::")
    }
    payload["score"] = rounded(score)
    payload["band"] = band_of(score) if score is not None else None
    payload["rank"] = rank
    payload["scores"] = {
        key: rounded(value) for key, value in entry["scores"].items()
    }
    for key in (
        "safety_margin_pct", "expected_return_pct", "base_income_pct",
        "max_drawdown_pct", "risk_free_rate_pct",
        "risk_adjusted_ratio", "valuation_reliance",
    ):
        payload[key] = rounded(payload.get(key), 2)
    return payload


def build_output(entries: list[dict], data_dir: Path, today: dt.date) -> dict:
    eligible = [entry for entry in entries if not entry["excluded_reasons"]]
    main = [entry for entry in eligible if entry["asset_type"] != "etf"]
    etfs = [entry for entry in eligible if entry["asset_type"] == "etf"]
    excluded = [entry for entry in entries if entry["excluded_reasons"]]

    profiles = {}
    for code, profile in PROFILES.items():
        ranked = sorted(main, key=lambda entry: -(entry[f"score::{code}"] or -1))
        profiles[code] = {
            "label": profile["label"],
            "description": profile["description"],
            "weights": profile["weights"],
            "items": [
                serialize_entry(entry, code, rank)
                for rank, entry in enumerate(ranked, 1)
            ],
        }

    etf_items = []
    for entry in etfs:
        payload = serialize_entry(entry, "balanced")
        payload["profile_scores"] = {
            code: rounded(entry.get(f"score::{code}"))
            for code in PROFILES
        }
        etf_items.append(payload)

    active_names = {entry["name"] for entry in eligible}
    buy_count = sum(1 for entry in main if "买入" in entry["verdict"])
    return {
        "schema_version": "1.0",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "as_of": today.isoformat(),
        "source": {
            "data_dir": str(data_dir),
            "cards": len({entry["name"] for entry in entries}),
            "ranking_units": len(entries),
        },
        "summary": {
            "covered_instruments": len(active_names),
            "main_board_units": len(main),
            "etf_units": len(etfs),
            "buy_candidates": buy_count,
            "excluded_units": len(excluded),
        },
        "default_profile": "balanced",
        "profiles": profiles,
        "etfs": etf_items,
        "excluded": [
            serialize_entry(entry, "balanced")
            for entry in excluded
        ],
        "notes": [
            "安全边际只在 safety_margin 维度计分，基础收益只取股息、增长和汇率，避免重复计算估值修复。",
            "估值历史分位只作展示，不参与打分。",
            "排序单元为标的 × 市场；同一公司的 A/H 两地属于同一经营敞口，仓位需合并。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成投资性价比排序 JSON")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out", default=None)
    parser.add_argument("--json", action="store_true", help="打印完整 JSON，不写文件")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"找不到数据卡目录 {data_dir}/", file=sys.stderr)
        return 1
    cards = []
    validate_file = load_card_validator()
    for path in sorted(data_dir.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"数据卡 JSON 无法解析：{path.name}: {exc}") from exc
        if not isinstance(card, dict) or not isinstance(card.get("markets"), list):
            continue
        if card.get("schema_version") != "1.2":
            raise RuntimeError(
                f"数据卡 schema 版本不是 1.2：{path.name} "
                f"({card.get('schema_version')!r})"
            )
        errors, _warnings = validate_file(path)
        if errors:
            raise RuntimeError(
                f"数据卡校验失败：{path.name}：" + "；".join(errors)
            )
        cards.append(card)
    if not cards:
        print(f"{data_dir}/ 下没有 schema 1.2 数据卡。", file=sys.stderr)
        return 1

    today = dt.date.today()
    latest = {}
    for card in cards:
        candidate_key = (
            str(card.get("analysis_date") or ""),
            str(card.get("generated_at") or ""),
        )
        current = latest.get(card["name"])
        if current is None or candidate_key > current[0]:
            latest[card["name"]] = (candidate_key, card)
    latest_cards = [item[1] for item in latest.values()]
    output = build_output(build_entries(latest_cards, today), data_dir, today)
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.json:
        print(rendered)
        return 0

    out_path = Path(args.out) if args.out else Path(f"投资性价比排序_{today.isoformat()}.json")
    out_path.write_text(rendered + "\n", encoding="utf-8")
    print(f"已写入 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
