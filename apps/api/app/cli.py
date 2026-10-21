from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="valuation-api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import-legacy", help="导入现有 JSON 数据卡")
    import_parser.add_argument("--data-dir", required=True)
    import_parser.add_argument("--reports-dir", required=True)
    args = parser.parse_args()

    if args.command == "import-legacy":
        raise SystemExit("legacy importer will be added in the next phase")


if __name__ == "__main__":
    main()
