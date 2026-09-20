from __future__ import annotations

import argparse

from .replay import run_replay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay ActionEvent JSONL against a rule set")
    parser.add_argument("--events", required=True, help="ActionEvent JSONL fixture")
    parser.add_argument("--rules", required=True, help="Rule set YAML")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_replay(args.events, args.rules)
    print(result.model_dump_json(indent=2, by_alias=True))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
