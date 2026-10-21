#!/usr/bin/env python3
"""通用数据的本地缓存（默认 24 小时），供 value-investing skill 取数时使用。

目录约定：<当前工作区>/common/<key>.json

用法：
  python3 scripts/cache.py get  <key> [--dir common] [--ttl 24]
  python3 scripts/cache.py put  <key> [--dir common] [--ttl 24] --data '<json 对象>'
  python3 scripts/cache.py put  <key> [--dir common] [--ttl 24] --data-file payload.json
  python3 scripts/cache.py list [--dir common]

get 的退出码：0 = 命中且未过期；3 = 过期；4 = 本地没有这个文件。
无论命中与否都会打印 JSON，「data」字段带回文件内容（过期时也能拿来兜底）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DEFAULT_DIR = "common"
DEFAULT_TTL = 24.0


def now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def parse_ts(text: object) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.astimezone()


def load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取 {path} 失败：{exc}", file=sys.stderr)
        return None
    if not isinstance(body, dict):
        print(f"{path} 顶层不是 JSON 对象，已忽略", file=sys.stderr)
        return None
    return body


def dump(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def freshness(body: dict, fallback_ttl: float) -> tuple[float | None, float, bool]:
    ts = parse_ts(body.get("updated_at", ""))
    try:
        ttl = float(body.get("ttl_hours", fallback_ttl))
    except (TypeError, ValueError):
        ttl = fallback_ttl
    age = None if ts is None else (now() - ts).total_seconds() / 3600
    return age, ttl, age is not None and age <= ttl


def cmd_get(args: argparse.Namespace) -> int:
    path = Path(args.dir) / f"{args.key}.json"
    body = load(path)
    if body is None:
        dump({"hit": False, "reason": "missing", "path": str(path), "data": None})
        return 4
    age, ttl, fresh = freshness(body, args.ttl)
    if fresh:
        reason = "fresh"
    elif age is None:
        reason = "no-timestamp"
    else:
        reason = "stale"
    dump(
        {
            "hit": fresh,
            "reason": reason,
            "path": str(path),
            "age_hours": None if age is None else round(age, 2),
            "ttl_hours": ttl,
            "data": body,
        }
    )
    return 0 if fresh else 3


def cmd_put(args: argparse.Namespace) -> int:
    raw = args.data if args.data is not None else (
        Path(args.data_file).read_text(encoding="utf-8") if args.data_file else None
    )
    if raw is None:
        print("put 需要 --data 或 --data-file", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"--data 不是合法 JSON：{exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("--data 顶层必须是 JSON 对象", file=sys.stderr)
        return 2

    path = Path(args.dir) / f"{args.key}.json"
    existed = path.is_file()
    body = load(path) or {}
    body.update(payload)
    body["key"] = args.key
    body["updated_at"] = now().isoformat(timespec="seconds")
    try:
        body["ttl_hours"] = float(payload.get("ttl_hours", args.ttl))
    except (TypeError, ValueError):
        body["ttl_hours"] = args.ttl

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)                      # 原子替换，避免并发写坏文件
    dump(
        {
            "ok": True,
            "path": str(path),
            "action": "updated" if existed else "created",
            "updated_at": body["updated_at"],
            "keys": sorted(payload),
        }
    )
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.dir)
    rows = []
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            body = load(path) or {}
            age, ttl, fresh = freshness(body, args.ttl)
            rows.append(
                {
                    "key": body.get("key", path.stem),
                    "path": str(path),
                    "updated_at": body.get("updated_at"),
                    "age_hours": None if age is None else round(age, 2),
                    "stale": not fresh,
                }
            )
    dump({"dir": str(root), "count": len(rows), "files": rows})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="通用数据本地缓存（默认 24 小时）")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--dir", default=DEFAULT_DIR, help=f"缓存目录，默认 {DEFAULT_DIR}/")
        sp.add_argument("--ttl", type=float, default=DEFAULT_TTL, help="有效期（小时），默认 24")

    for name, help_text in (("get", "读缓存并判断是否过期"), ("put", "写入 / 更新缓存")):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("key", help="数据键名，小写英文 slug，如 treasury_10y")
        add_common(sp)
        if name == "put":
            sp.add_argument("--data", help="要写入的 JSON 对象")
            sp.add_argument("--data-file", help="要写入的 JSON 文件")

    sp = sub.add_parser("list", help="列出缓存目录里的文件与新鲜度")
    add_common(sp)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"get", "put"} and not KEY_RE.match(args.key):
        print("key 只能用小写字母、数字、点、下划线和连字符（如 treasury_10y）", file=sys.stderr)
        return 2
    return {"get": cmd_get, "put": cmd_put, "list": cmd_list}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
