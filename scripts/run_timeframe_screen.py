"""One-off diagnostic: does the mean-reversion signal do better on coarser
bars? (Task 0.3 Phase A.2 — isolates the fee-drag/overtrading hypothesis from
the Bollinger-lookback question already tested in the hour-scale re-run.)

Resamples the already-ingested 1s Binance corpus (no new ingestion) to 1min
and 5min bars via `backtest.resample.resample_ohlcv`, and screens a small,
bounded set of configs (the shape family that performed best in the
hour-scale round: bb3600-equivalent lookback, mean_revert exit, loose RSI
thresholds) at each resolution.

`bollinger.period` is converted to preserve the same *real-world* 1h lookback
at each resolution (60 bars @ 1min, 12 bars @ 5min); `time_stop_s` stays in
real seconds (the exit logic is timeframe-aware via `_bar_seconds`);
`rsi.period` is kept as the same *bar count* (5/14) at each resolution, which
means it also represents a longer real-world window at coarser
resolutions — an accepted conflation for this specific exploratory test, not
a clean single-variable isolation. Documented in docs/task0_1_status.md.

    uv run python scripts/run_timeframe_screen.py [--symbols BTCUSDT,...] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

from scalpbot.backtest.costs import load_cost_params
from scalpbot.backtest.resample import resample_ohlcv
from scalpbot.backtest.research_ledger import DEFAULT_LEDGER_PATH
from scalpbot.backtest.vector_screen import screen_grid
from scalpbot.core.strategy import BollingerConfig, RsiConfig, StrategyConfig
from scalpbot.data.config import load_data_config
from scalpbot.data.loader import load_partitions

PILOT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
_OHLCV_COLUMNS = ["open_time_ms", "open", "high", "low", "close", "volume"]

# timeframe -> (bucket_ms, bollinger.period for an equivalent 1h real-world lookback)
_RESOLUTIONS = {
    "1m": (60_000, 60),
    "5m": (300_000, 12),
}


def _build_configs(timeframe: str, bollinger_period: int) -> list[StrategyConfig]:
    configs = []
    for sigma in (2.5, 3.0):
        for rsi_period in (5, 14):
            for oversold, overbought in ((15.0, 85.0), (20.0, 80.0)):
                name = (
                    f"tf_{timeframe}_bb{bollinger_period}_{sigma:g}sd_rsi{rsi_period}_"
                    f"{oversold:g}-{overbought:g}"
                )
                configs.append(
                    StrategyConfig(
                        name=name,
                        status="CANDIDATE",
                        timeframe=timeframe,
                        bollinger=BollingerConfig(period=bollinger_period, sigma=sigma),
                        rsi=RsiConfig(period=rsi_period, overbought=overbought, oversold=oversold),
                        exits={
                            "mode": "mean_revert",
                            "stop_pct": 6.0,
                            "target": "middle_band",
                            "time_stop_s": 7200,
                        },
                    )
                )
    return configs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config", default="configs/research.yaml")
    parser.add_argument("--symbols", default=",".join(PILOT_SYMBOLS))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    args = parser.parse_args()

    data_root = Path(args.data_root)
    data_cfg = load_data_config(args.config)
    cost_params = load_cost_params(args.config)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    holdout_start_ms = data_cfg.signal_corpus.holdout_start_ms

    all_rows: list[dict] = []
    for symbol in symbols:
        full = load_partitions(data_root, "binance", "klines", symbol, "1s", _OHLCV_COLUMNS)
        pre_holdout = full.filter(pl.col("open_time_ms") < holdout_start_ms)
        if pre_holdout.height == 0:
            print(f"[{symbol}] no pre-holdout data on disk, skipping")
            continue

        for timeframe, (bucket_ms, bollinger_period) in _RESOLUTIONS.items():
            resampled = resample_ohlcv(pre_holdout, bucket_ms)
            configs = _build_configs(timeframe, bollinger_period)
            data_range = (
                f"{data_cfg.signal_corpus.start}..{data_cfg.signal_corpus.holdout_start} "
                f"(pre-holdout, resampled {timeframe})"
            )
            result = screen_grid(
                resampled, symbol, configs, cost_params, args.ledger, data_range=data_range
            )
            all_rows.extend(result.to_dicts())

    all_rows.sort(key=lambda r: r["expectancy_r"], reverse=True)

    header = (
        f"{'config_name':<55} {'symbol':<10} {'n_trades':>8} {'expectancy_r':>13} "
        f"{'t_stat':>8} {'win_rate':>9}"
    )
    print(header)
    print("-" * len(header))
    for row in all_rows:
        print(
            f"{row['config_name']:<55} {row['symbol']:<10} {row['n_trades']:>8} "
            f"{row['expectancy_r']:>13.4f} {row['t_stat']:>8.2f} {row['win_rate']:>9.2%}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
