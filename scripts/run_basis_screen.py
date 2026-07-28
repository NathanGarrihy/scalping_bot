"""Screen the cross-venue basis-dislocation signal (Task 0.3 "zoom out" round,
Phase D — see `backtest/basis_signal.py` for the economic rationale and the
sample-size caveat: the Hyperliquid corpus only covers ~90 days pre-holdout
at 1h resolution, an order of magnitude smaller than the price-based rounds).

Bracket exits only, `mean_revert` direction only (basis dislocation is
inherently a reversion bet — no momentum variant here) — kept a small,
bounded grid given the sample-size caveat above; not folded into the main
`screen:` config block since it needs a different data pipeline
(`build_basis_corpus`, not a bare kline load) and timeframe (1h).

    uv run python scripts/run_basis_screen.py [--symbols BTCUSDT,...] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import polars as pl

from scalpbot.backtest.basis_signal import build_basis_corpus
from scalpbot.backtest.costs import load_cost_params
from scalpbot.backtest.research_ledger import DEFAULT_LEDGER_PATH
from scalpbot.backtest.vector_screen import screen_grid
from scalpbot.core.strategy import BollingerConfig, RsiConfig, StrategyConfig
from scalpbot.data.config import load_data_config
from scalpbot.data.hyperliquid_candles import OUTPUT_INTERVAL as HL_INTERVAL
from scalpbot.data.hyperliquid_candles import SYMBOL_MAP
from scalpbot.data.loader import load_partitions

PILOT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
_BINANCE_COLUMNS = ["open_time_ms", "open", "high", "low", "close", "volume"]
_HL_COLUMNS = ["open_time_ms", "open", "high", "low", "close"]


def _build_configs() -> list[StrategyConfig]:
    configs = []
    for period in (24, 72, 168):  # 1 day / 3 days / 1 week, in 1h bars
        for sigma in (2.0, 2.5, 3.0):
            for rsi_period in (6, 24):  # 6h / 24h
                for oversold, overbought in ((15.0, 85.0), (20.0, 80.0)):
                    name = (
                        f"basis_bb{period}_{sigma:g}sd_rsi{rsi_period}_{oversold:g}-{overbought:g}"
                    )
                    configs.append(
                        StrategyConfig(
                            name=name,
                            status="CANDIDATE",
                            timeframe="1h",
                            bollinger=BollingerConfig(period=period, sigma=sigma),
                            rsi=RsiConfig(
                                period=rsi_period, overbought=overbought, oversold=oversold
                            ),
                            exits={"mode": "bracket", "stop_pct": 6.0, "take_profit_pct": 2.0},
                            signal_direction="mean_revert",
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
    configs = _build_configs()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    holdout_start_ms = data_cfg.signal_corpus.holdout_start_ms

    print(f"Screening {len(configs)} basis configs x {len(symbols)} symbols\n", flush=True)

    all_rows: list[dict] = []
    for symbol in symbols:
        coin = SYMBOL_MAP.get(symbol)
        if coin is None:
            print(f"[{symbol}] no Hyperliquid mapping, skipping", flush=True)
            continue

        binance_1s = load_partitions(data_root, "binance", "klines", symbol, "1s", _BINANCE_COLUMNS)
        binance_1s = binance_1s.filter(pl.col("open_time_ms") < holdout_start_ms)
        hl_1h = load_partitions(data_root, "hyperliquid", "candles", coin, HL_INTERVAL, _HL_COLUMNS)
        if binance_1s.height == 0 or hl_1h.height == 0:
            print(f"[{symbol}] missing Binance or Hyperliquid data, skipping", flush=True)
            continue

        corpus = build_basis_corpus(binance_1s, hl_1h)
        print(f"[{symbol}] basis corpus: {corpus.height} overlapping hourly bars", flush=True)
        if corpus.height == 0:
            continue

        data_range = (
            f"{data_cfg.signal_corpus.start}..{data_cfg.signal_corpus.holdout_start} "
            "(basis, pre-holdout)"
        )
        result = screen_grid(
            corpus,
            symbol,
            configs,
            cost_params,
            args.ledger,
            data_range=data_range,
            source_column="basis_bps",
        )
        rows = result.to_dicts()
        all_rows.extend(rows)
        best = max(rows, key=lambda r: r["expectancy_r"]) if rows else None
        best_str = (
            f"best={best['expectancy_r']:.4f}R ({best['config_name']})" if best else "no configs"
        )
        print(f"[{symbol}] done — {len(rows)} configs, {best_str}", flush=True)

    all_rows.sort(key=lambda r: r["expectancy_r"], reverse=True)

    header = (
        f"{'config_name':<45} {'symbol':<10} {'n_trades':>8} {'expectancy_r':>13} "
        f"{'t_stat':>8} {'win_rate':>9}"
    )
    lines = [header, "-" * len(header)]
    for row in all_rows:
        lines.append(
            f"{row['config_name']:<45} {row['symbol']:<10} {row['n_trades']:>8} "
            f"{row['expectancy_r']:>13.4f} {row['t_stat']:>8.2f} {row['win_rate']:>9.2%}"
        )
    text = "\n".join(lines)
    print(text)

    reports_dir = data_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"basis_screen_report_{int(time.time())}.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"\n(saved to {out_path})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
