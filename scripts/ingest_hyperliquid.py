"""Backfill the Hyperliquid venue-calibration corpus (PLAN.md §3, Task 0.1).

Downloads info-API `candleSnapshot` 1h candles for the pilot basket, writing
Parquet partitions under `data/hyperliquid/candles/`. Idempotent/resumable:
re-running skips any already-complete partition. `end=None` (the default)
resolves to the last fully-closed UTC day.

    uv run python scripts/ingest_hyperliquid.py [--coins BTC,ETH] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from scalpbot.data.config import load_data_config
from scalpbot.data.hyperliquid_candles import SYMBOL_MAP, ingest_symbol_range

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
            print(f"[{coin}] ingesting {cfg.venue_corpus.start} -> present")
            summary = ingest_symbol_range(
                coin,
                cfg.venue_corpus.start,
                cfg.venue_corpus.end,
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
