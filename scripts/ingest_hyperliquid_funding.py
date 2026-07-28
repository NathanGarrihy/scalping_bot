"""Backfill Hyperliquid funding-rate history (PLAN.md §3, Task 0.3 "zoom out"
round, Phase E).

Downloads info-API `fundingHistory` for the pilot basket, writing Parquet
partitions under `data/hyperliquid/funding/`. Idempotent/resumable — same
pattern as `scripts/ingest_hyperliquid.py`. Defaults to the *signal-research*
corpus's date range, not the shorter venue-corpus window: unlike
`candleSnapshot`, `fundingHistory` isn't a rolling cache (verified
empirically — see `data/hyperliquid_funding.py`), so it can actually cover
the full 2024-07-01+ window.

    uv run python scripts/ingest_hyperliquid_funding.py [--coins BTC,ETH] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from scalpbot.data.config import load_data_config
from scalpbot.data.hyperliquid_candles import SYMBOL_MAP
from scalpbot.data.hyperliquid_funding import ingest_symbol_range

PILOT_COINS = tuple(SYMBOL_MAP.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coins", default=",".join(PILOT_COINS))
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config", default="configs/research.yaml")
    args = parser.parse_args()

    coins = [c.strip() for c in args.coins.split(",") if c.strip()]
    cfg = load_data_config(args.config)
    data_root = Path(args.data_root)

    exit_code = 0
    with httpx.Client() as client:
        for coin in coins:
            print(f"[{coin}] ingesting {cfg.signal_corpus.start} -> {cfg.signal_corpus.end}")
            summary = ingest_symbol_range(
                coin,
                cfg.signal_corpus.start,
                cfg.signal_corpus.end,
                data_root=data_root,
                client=client,
            )
            print(
                f"[{coin}] total={summary.days_total} fetched={summary.days_fetched} "
                f"skipped_existing={summary.days_skipped_existing} "
                f"empty={summary.days_empty} failed={summary.days_failed}"
            )
            if summary.failed_days:
                print(f"[{coin}] FAILED DAYS: {summary.failed_days}")
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
