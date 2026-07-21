"""Offline command-line entry point for the full Jimbo bot shell."""

from __future__ import annotations

import argparse

from .app import FullBotApplication
from .runtime import FullBotRuntime, live_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jimbo full-bot application shell")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="print the safe offline startup report (the only Step 1 mode)",
    )
    parser.add_argument("--live", action="store_true", help="run the playable Step 7 prototype")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.offline and not args.live:
        parser.error("Step 1 supports only --offline unless --live is explicitly selected")
    if args.offline and args.live:
        parser.error("choose only one of --offline or --live")
    if args.live:
        FullBotRuntime(live_config()).run_forever()
        return 0
    print(FullBotApplication.offline().run_offline().as_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
