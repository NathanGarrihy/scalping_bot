"""Build the Task 0.2 universe time series from already-ingested Binance
klines (PLAN.md §3).

Ranks candidate symbols by trailing 30-day quote volume at each monthly
rebalance date (no lookahead — see `data/universe.py`), applies the
listing-age floor, and writes the result as Parquet. `spread_bps_max` is
parsed from `configs/research.yaml`'s `universe:` block but not enforced —
no historical spread data exists in either ingested corpus; see
`data/universe.py`'s module docstring.

    uv run python scripts/build_universe.py [--symbols BTCUSDT,...] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

from scalpbot.data.config import load_data_config
from scalpbot.data.loader import load_partitions
from scalpbot.data.universe import (
    aggregate_daily_quote_volume,
    compute_universe,
    load_universe_config,
    write_universe_file,
)

_VOLUME_COLUMNS = ["open_time_ms", "quote_volume"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config", default="configs/research.yaml")
    parser.add_argument("--symbols", required=True, help="comma-separated candidate pool")
    parser.add_argument("--out", default="data/universe/universe.parquet")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    data_cfg = load_data_config(args.config)
    universe_cfg = load_universe_config(args.config)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    daily_frames = []
    for symbol in symbols:
        klines = load_partitions(data_root, "binance", "klines", symbol, "1s", _VOLUME_COLUMNS)
        if klines.height == 0:
            print(f"[{symbol}] no data on disk, skipping")
            continue
        daily_frames.append(aggregate_daily_quote_volume(klines, symbol))

    if not daily_frames:
        print("no candidate symbols had data on disk — nothing to do")
        return 1

    daily_volume = pl.concat(daily_frames)
    memberships = compute_universe(
        daily_volume, universe_cfg, data_cfg.signal_corpus.start, data_cfg.signal_corpus.end
    )

    write_universe_file(memberships, args.out)

    n_dates = len({m.rebalance_date for m in memberships})
    print(f"{len(memberships)} memberships across {n_dates} rebalance dates -> {args.out}")

    latest_date = max(m.rebalance_date for m in memberships)
    latest_in_universe = sorted(
        m.symbol for m in memberships if m.rebalance_date == latest_date and m.in_universe
    )
    print(f"in-universe as of {latest_date}: {latest_in_universe}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
