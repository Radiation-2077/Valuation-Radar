from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


def parse_report_detail(html_path: Path) -> dict[str, Any]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    sections: list[dict[str, Any]] = []
    for section in soup.select("section"):
        title_node = section.find("h2", recursive=False)
        if title_node is None:
            continue
        title = clean_text(title_node)
        blocks = parse_children(section)
        sections.append({"title": title, "blocks": blocks})

    final_node = soup.select_one(".final")
    if final_node is not None:
        sections.append(
            {
                "title": clean_text(final_node.find("h2")) or "关键结论",
                "blocks": parse_children(final_node),
            }
        )

    foot_node = soup.select_one(".foot")
    foot = clean_text(foot_node) if foot_node is not None else ""
    return {"sections": sections, "foot": foot}


def parse_children(root: Tag, *, skip_heading: bool = True) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    skipped = False
    for child in root.children:
        if not isinstance(child, Tag):
            continue
        if skip_heading and not skipped and child.name == "h2":
            skipped = True
            continue
        block = parse_block(child)
        if block is not None:
            blocks.append(block)
    return blocks


def parse_block(node: Tag) -> dict[str, Any] | None:
    classes = set(node.get("class") or [])
    if node.name in {"h3", "h4"}:
        return {"type": "heading", "level": int(node.name[1]), "text": clean_text(node)}
    if node.name == "p":
        text = clean_text(node)
        return {"type": "paragraph", "text": text, "note": "note" in classes} if text else None
    if node.name == "table":
        return parse_table(node)
    if "scores" in classes:
        items = []
        for row in node.select(":scope > .score"):
            bar = row.find("i")
            if bar is None:
                continue
            items.append(
                {
                    "label": clean_text(row.find("span")),
                    "score": clean_text(row.find("b")),
                    "width": extract_percent(bar),
                    "tone": "negative" if "r" in (bar.get("class") or []) else "positive",
                }
            )
        return {"type": "scores", "items": items}
    if "gauges" in classes:
        items = []
        for gauge in node.select(".gauge"):
            numeric = clean_text(gauge.select_one(".gauge-num"))
            fill = gauge.select_one(".g-fill")
            tone = next(
                (
                    name
                    for name in ("c-pos", "c-acc", "c-warn", "c-neg")
                    if name in (fill.get("class") or [])
                ),
                "c-pos",
            ) if fill is not None else "c-pos"
            items.append(
                {
                    "label": clean_text(gauge.select_one(".gauge-label")),
                    "value": numeric,
                    "tone": tone.replace("c-", ""),
                }
            )
        return {"type": "gauges", "items": items}
    if "mrow" in classes:
        return {
            "type": "metric_cards",
            "items": [
                {
                    "label": clean_text(metric.find("small")),
                    "value": clean_text(metric.find("b")),
                    "detail": clean_text(metric.find("em")),
                }
                for metric in node.select(".metric")
            ],
        }
    if "tbl-scroll" in classes:
        table = node.find("table")
        return parse_table(table) if table is not None else None
    if "grid2" in classes or "grid21" in classes:
        columns = []
        for child in node.find_all(recursive=False):
            if isinstance(child, Tag):
                columns.append(parse_children(child, skip_heading=False))
        return {"type": "grid", "columns": columns}
    if "callout" in classes:
        tone = "info"
        for name in ("pos", "warn", "neg", "info"):
            if name in classes:
                tone = name
                break
        return {
            "type": "callout",
            "tone": tone,
            "title": clean_text(node.find("b")),
            "body": clean_text(node.find("span")),
        }
    if "scale" in classes:
        mark = node.select_one(".scale-mark")
        return {
            "type": "scale",
            "position": extract_percent(mark, "left"),
            "label": clean_text(mark),
            "stops": [
                {"label": clean_text(stop), "active": "on" in (stop.get("class") or [])}
                for stop in node.select(".scale-stops span")
            ],
        }
    if "vbars" in classes:
        items = []
        for bar in node.select(".vb"):
            items.append(
                {
                    "label": clean_text(bar.find("em")),
                    "height": extract_percent(bar.find("i"), "height"),
                    "highlight": "hi" in (bar.get("class") or []),
                }
            )
        return {"type": "scenario_bars", "items": items}
    if "rangebar" in classes:
        fill = node.select_one(".rb-fill")
        pin = node.select_one(".rb-pin")
        return {
            "type": "range_bar",
            "fill_left": extract_percent(fill, "left"),
            "fill_width": extract_percent(fill, "width"),
            "pin_left": extract_percent(pin, "left"),
            "pin_label": clean_text(pin.find("span") if pin is not None else None),
            "axis": [clean_text(item) for item in node.select(".rb-axis span")],
        }
    if "posblock" in classes:
        donut = node.select_one(".donut")
        text_root = node.find_all(recursive=False)
        action = node.select_one(".tag")
        notes = node.select(".note")
        return {
            "type": "position_block",
            "percentage": extract_css_number(donut, "--p"),
            "center_value": clean_text(donut.find("b")) if donut else "",
            "center_label": clean_text(donut.find("span")) if donut else "",
            "action": clean_text(action),
            "notes": [clean_text(item) for item in notes],
            "right_blocks": (
                parse_children(text_root[-1], skip_heading=False)
                if len(text_root) > 1
                else []
            ),
        }
    if "donut" in classes:
        parent = node.parent
        return {
            "type": "donut",
            "percentage": extract_css_number(node, "--p"),
            "value": clean_text(node.find("b")),
            "label": clean_text(node.find("span")),
            "background": node.get("style", ""),
            "context": clean_text(parent) if parent else "",
        }
    if "steps" in classes:
        return {
            "type": "steps",
            "items": [
                {
                    "title": clean_text(item.find("b")),
                    "body": clean_text(item.find("span")),
                    "active": "on" in (item.get("class") or []),
                }
                for item in node.find_all("li", recursive=False)
            ],
        }
    if "risk-grid" in classes:
        risks = []
        for card in node.select(".risk-card"):
            header = card.find("header")
            risks.append(
                {
                    "title": clean_text(header.find("b")) if header else "",
                    "probability": clean_text(header.select_one(".badge")) if header else "",
                    "body": clean_text(card.find("p")),
                    "mitigation": clean_text(card.select_one(".mitig")),
                    "level": next(
                        (
                            name.replace("lv-", "")
                            for name in (card.get("class") or [])
                            if name.startswith("lv-")
                        ),
                        "m",
                    ),
                }
            )
        return {"type": "risk_cards", "items": risks}
    if "stack" in classes:
        return {
            "type": "return_stack",
            "items": [
                {
                    "label": clean_text(segment),
                    "width": extract_percent(segment, "width"),
                    "color": extract_inline_style(segment, "background"),
                }
                for segment in node.select(".seg")
            ],
        }
    if "final" in classes:
        return None
    if "foot" in classes:
        return {"type": "paragraph", "text": clean_text(node), "note": True}
    if "sub" in classes or "note" in classes:
        return {"type": "paragraph", "text": clean_text(node), "note": True}

    children = parse_children(node, skip_heading=False)
    return {"type": "group", "blocks": children} if children else None


def parse_table(table: Tag) -> dict[str, Any]:
    rows: list[list[str]] = []
    headers: list[str] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        values = [clean_text(cell) for cell in cells]
        if not values:
            continue
        if tr.find("th", recursive=False) and not headers:
            headers = values
        else:
            rows.append(values)
    return {"type": "table", "headers": headers, "rows": rows}


def clean_text(node: Tag | None) -> str:
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    text = re.sub(r"[ \t\r\f\v]+", " ", node.get_text(" ", strip=True))
    return text.replace(" \n ", "\n").strip()


def extract_percent(node: Tag | None, property_name: str = "width") -> float:
    if node is None:
        return 0.0
    style = str(node.get("style") or "")
    match = re.search(rf"{re.escape(property_name)}\s*:\s*([\d.]+)%", style)
    return float(match.group(1)) if match else 0.0


def extract_css_number(node: Tag | None, property_name: str) -> float:
    if node is None:
        return 0.0
    style = str(node.get("style") or "")
    match = re.search(rf"{re.escape(property_name)}\s*:\s*([\d.]+)", style)
    return float(match.group(1)) if match else 0.0


def extract_inline_style(node: Tag | None, property_name: str) -> str:
    if node is None:
        return ""
    style = str(node.get("style") or "")
    match = re.search(rf"{re.escape(property_name)}\s*:\s*([^;]+)", style)
    return match.group(1).strip() if match else ""
