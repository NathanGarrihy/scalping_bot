"""Screen the funding-rate-extreme signal (Task 0.3 "zoom out" round, Phase E
— see `backtest/funding_signal.py` for the economic rationale and the
inherited sample-size caveat: the tradeable-price side is still bounded by
Hyperliquid's ~90-day pre-holdout candle window, same as Round 4's basis
probe, even though the funding series itself covers 2024-07-01+).

Bracket exits only, `mean_revert` direction only (extreme funding reverting
is the economic bet: `mean_revert`'s existing entry logic already maps
correctly — long when funding_pressure pierces its lower band (unusually
negative/cheap funding), short when it pierces the upper band (unusually
positive/crowded-long funding) — no new direction logic needed).

Accepted conflation for this bounded exploratory test: `bollinger.period`
does double duty as both the trailing-hours window `funding_pressure` sums
over *and* the Bollinger lookback that then bands that already-smoothed
series — coupling "how much funding to accumulate" and "how far back to
judge whether that's extreme" instead of treating them as independent axes.
Simpler grid, cheaper to run; a follow-up could decouple them if this round
looks promising enough to warrant it.

    uv run python scripts/run_funding_screen.py [--symbols BTCUSDT,...] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import polars as pl

from scalpbot.backtest.costs import load_cost_params
from scalpbot.backtest.funding_signal import build_funding_corpus
from scalpbot.backtest.research_ledger import DEFAULT_LEDGER_PATH
from scalpbot.backtest.vector_screen import screen_grid
from scalpbot.core.strategy import BollingerConfig, RsiConfig, StrategyConfig
from scalpbot.data.config import load_data_config
from scalpbot.data.hyperliquid_candles import OUTPUT_INTERVAL as HL_INTERVAL
from scalpbot.data.hyperliquid_candles import SYMBOL_MAP
from scalpbot.data.loader import load_partitions

PILOT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
_HL_CANDLE_COLUMNS = ["open_time_ms", "open", "high", "low", "close"]
_HL_FUNDING_COLUMNS = ["open_time_ms", "funding_rate"]


def _build_configs() -> list[StrategyConfig]:
    configs = []
    for trailing_hours in (12, 24, 72):  # 12h / 1day / 3day accumulated funding pressure
        for sigma in (2.0, 2.5, 3.0):
            for rsi_period in (6, 24):
                for oversold, overbought in ((15.0, 85.0), (20.0, 80.0)):
                    name = (
                        f"funding_bb{trailing_hours}_{sigma:g}sd_rsi{rsi_period}_"
                        f"{oversold:g}-{overbought:g}"
                    )
                    configs.append(
                        StrategyConfig(
                            name=name,
                            status="CANDIDATE",
                            timeframe="1h",
                            bollinger=BollingerConfig(period=trailing_hours, sigma=sigma),
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

    print(f"Screening {len(configs)} funding configs x {len(symbols)} symbols\n", flush=True)

    all_rows: list[dict] = []
    for symbol in symbols:
        coin = SYMBOL_MAP.get(symbol)
        if coin is None:
            print(f"[{symbol}] no Hyperliquid mapping, skipping", flush=True)
            continue

        hl_candles = load_partitions(
            data_root, "hyperliquid", "candles", coin, HL_INTERVAL, _HL_CANDLE_COLUMNS
        )
        # HL candles span past the holdout boundary (the corpus wasn't
        # ingested with holdout quarantine in mind) — filter here the same
        # way run_basis_screen.py filters Binance data, or the screen would
        # trade on holdout rows. Funding history itself is left unfiltered:
        # funding_pressure at time T only ever sums funding at times <= T
        # (causal), so it can't leak future information regardless.
        hl_candles = hl_candles.filter(
            pl.col("open_time_ms") < data_cfg.signal_corpus.holdout_start_ms
        )
        funding_history = load_partitions(
            data_root, "hyperliquid", "funding", coin, HL_INTERVAL, _HL_FUNDING_COLUMNS
        )
        if hl_candles.height == 0 or funding_history.height == 0:
            print(f"[{symbol}] missing HL candles or funding history, skipping", flush=True)
            continue

        # Bollinger period IS the trailing-hours window used to build
        # funding_pressure below — each config's period sets its own corpus,
        # so the indicator cache in screen_grid still has to recompute per
        # period (unavoidable here since the source series itself changes,
        # not just the rolling window over a fixed series).
        for trailing_hours in {c.bollinger.period for c in configs}:
            corpus = build_funding_corpus(
                hl_candles, funding_history, trailing_hours=trailing_hours
            )
            if corpus.height == 0:
                continue
            subset = [c for c in configs if c.bollinger.period == trailing_hours]
            print(
                f"[{symbol}] trailing_hours={trailing_hours}: "
                f"{corpus.height} overlapping hourly bars",
                flush=True,
            )
            data_range = (
                f"{data_cfg.signal_corpus.start}..{data_cfg.signal_corpus.holdout_start} "
                "(funding, pre-holdout)"
            )
            result = screen_grid(
                corpus,
                symbol,
                subset,
                cost_params,
                args.ledger,
                data_range=data_range,
                source_column="funding_pressure",
            )
            all_rows.extend(result.to_dicts())

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
    out_path = reports_dir / f"funding_screen_report_{int(time.time())}.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"\n(saved to {out_path})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
