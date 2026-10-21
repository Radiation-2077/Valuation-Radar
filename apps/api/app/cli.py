from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.importer import import_legacy_cards


def main() -> None:
    parser = argparse.ArgumentParser(prog="valuation-api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import-legacy", help="导入现有 JSON 数据卡")
    import_parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()

    if args.command == "import-legacy":
        with SessionLocal() as session:
            summary = import_legacy_cards(
                session,
                data_dir=Path(args.data_dir),
            )
        print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
