from __future__ import annotations

import argparse
import sys

from .digest import build_daily_digest, write_daily_digest
from .pipeline import collect_all
from .telegram import send_latest_digest


def main() -> None:
    parser = argparse.ArgumentParser(description="FeedHub CLI")
    parser.add_argument("command", choices=["collect", "digest", "push-telegram"])
    args = parser.parse_args()

    try:
        if args.command == "collect":
            items = collect_all()
            print(f"Collected {len(items)} unique items.")
            return

        if args.command == "push-telegram":
            digest_path = send_latest_digest()
            print(f"Sent digest from {digest_path} to Telegram.")
            return

        digest_path = write_daily_digest()
        print(build_daily_digest())
        print(f"Digest written to {digest_path}")
    except Exception as exc:
        print(f"FeedHub error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
