"""Run the Stage 1 coarse parameter screen over the real signal corpus
(PLAN.md §3, Task 0.3).

Screening only — never cited as gate evidence. Prints a ranked summary
(highest expectancy_r first) and appends every evaluated config to
`research/ledger.md`, per symbol. The holdout window (per
`configs/research.yaml`'s `holdout_months`) is excluded, matching
`scripts/data_report.py`.

    uv run python scripts/run_screen.py [--symbols BTCUSDT,ETHUSDT] [--data-root data]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import polars as pl

from scalpbot.backtest.costs import load_cost_params
from scalpbot.backtest.research_ledger import DEFAULT_LEDGER_PATH
from scalpbot.backtest.screen_config import iter_configs, load_screen_config
from scalpbot.backtest.vector_screen import screen_grid
from scalpbot.data.config import load_data_config
from scalpbot.data.loader import load_partitions

PILOT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
_OHLCV_COLUMNS = ["open_time_ms", "open", "high", "low", "close", "volume"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config", default="configs/research.yaml")
    parser.add_argument("--symbols", default=",".join(PILOT_SYMBOLS))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument(
        "--signal-direction",
        choices=("mean_revert", "momentum"),
        default=None,
        help="restrict to one signal_direction — the full grid can exceed a single "
        "invocation's time budget; split by direction (and --symbols) to fit",
    )
    parser.add_argument(
        "--bollinger-period",
        type=int,
        default=None,
        help="restrict to one bollinger.period value (bars) — a further split lever "
        "when --signal-direction alone still doesn't fit the time budget",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root)
    data_cfg = load_data_config(args.config)
    cost_params = load_cost_params(args.config)
    screen_cfg = load_screen_config(args.config)
    configs = list(iter_configs(screen_cfg))
    if args.signal_direction is not None:
        configs = [c for c in configs if c.signal_direction == args.signal_direction]
    if args.bollinger_period is not None:
        configs = [c for c in configs if c.bollinger.period == args.bollinger_period]
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    holdout_start_ms = data_cfg.signal_corpus.holdout_start_ms
    data_range = (
        f"{data_cfg.signal_corpus.start}..{data_cfg.signal_corpus.holdout_start} (pre-holdout)"
    )

    print(f"Screening {len(configs)} configs x {len(symbols)} symbols ({data_range})\n", flush=True)

    all_rows: list[dict] = []
    for symbol in symbols:
        full = load_partitions(data_root, "binance", "klines", symbol, "1s", _OHLCV_COLUMNS)
        pre_holdout = full.filter(pl.col("open_time_ms") < holdout_start_ms)
        if pre_holdout.height == 0:
            print(f"[{symbol}] no pre-holdout data on disk, skipping", flush=True)
            continue

        result = screen_grid(
            pre_holdout, symbol, configs, cost_params, args.ledger, data_range=data_range
        )
        rows = result.to_dicts()
        all_rows.extend(rows)
        best = max(rows, key=lambda r: r["expectancy_r"]) if rows else None
        best_str = (
            f"best={best['expectancy_r']:.4f}R ({best['config_name']})" if best else "no configs"
        )
        print(f"[{symbol}] done — {len(rows)} configs, {best_str}", flush=True)

    all_rows.sort(key=lambda r: r["expectancy_r"], reverse=True)
    lines: list[str] = []

    header = (
        f"{'config_name':<45} {'symbol':<10} {'n_trades':>8} {'expectancy_r':>13} "
        f"{'t_stat':>8} {'win_rate':>9}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for row in all_rows:
        lines.append(
            f"{row['config_name']:<45} {row['symbol']:<10} {row['n_trades']:>8} "
            f"{row['expectancy_r']:>13.4f} {row['t_stat']:>8.2f} {row['win_rate']:>9.2%}"
        )
    text = "\n".join(lines)
    print(text)

    reports_dir = data_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"screen_report_{int(time.time())}.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"\n(saved to {out_path})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
