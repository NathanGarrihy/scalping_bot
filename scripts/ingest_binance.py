"""Backfill the Binance signal-research corpus (PLAN.md §3, Task 0.1).

Downloads USD-M futures aggTrades and resamples to 1s OHLCV bars for the
pilot basket, writing Parquet partitions under `data/binance/klines/`.
Idempotent/resumable: re-running skips any already-complete partition.

    uv run python scripts/ingest_binance.py [--symbols BTCUSDT,ETHUSDT] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from scalpbot.data.binance_archive import ingest_symbol_range
from scalpbot.data.config import load_data_config

PILOT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(PILOT_SYMBOLS))
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config", default="configs/research.yaml")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    cfg = load_data_config(args.config)
    data_root = Path(args.data_root)

    exit_code = 0
    with httpx.Client() as client:
        for symbol in symbols:
            print(f"[{symbol}] ingesting {cfg.signal_corpus.start} -> {cfg.signal_corpus.end}")
            summary = ingest_symbol_range(
                symbol,
                cfg.signal_corpus.start,
                cfg.signal_corpus.end,
                data_root=data_root,
                client=client,
            )
            print(
                f"[{symbol}] total={summary.days_total} fetched={summary.days_fetched} "
                f"skipped_existing={summary.days_skipped_existing} "
                f"skipped_not_listed={summary.days_skipped_not_listed} "
                f"failed={summary.days_failed} first_available={summary.first_available_day}"
            )
            if summary.failed_days:
                print(f"[{symbol}] FAILED DAYS: {summary.failed_days}")
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
