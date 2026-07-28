"""Vectorized (polars) coarse grid screen — Stage 1 of Task 0.3.

Prunes dead parameter regions cheaply before the event-driven engine (Stage
2) runs. Screening only: results are never cited as gate evidence (PLAN.md
§3, Task 0.3). Every configuration screened gets a research-ledger row via
`research_ledger.append_row` (multiple-testing honesty, CLAUDE.md).

Deliberately optimistic on fills — a signal fills at its own trigger price,
with no queue position or trade-through requirement — while applying the
*same* honest cost model (`costs.py`) Stage 2 will use. That makes this
screen's expectancy an upper bound: if the whole grid comes back below the
gate's 0.05R bar even under optimistic fills, the strategy family is dead.
`fills.py`'s hostile trade-through model is deliberately not used here — see
Task 0.3's two-stage design in PLAN.md.

Screens two structurally different signal families via `StrategyConfig.signal_direction`:
`mean_revert` (PLAN.md's named anchor — bet a band-pierce reverts) and `momentum` (the
Task 0.3 "zoom out" round's contrast hypothesis — bet it continues). Same indicators,
same cost model, same exit mechanics; only which side of the pierce triggers long vs.
short flips. See `_evaluate_config`.

No dependency on `scalpbot.core` — the indicator math here is a screening
approximation (polars `ewm_mean` for Wilder-style RSI, rolling mean/std for
Bollinger bands), not `core.indicators`'s O(1) bit-exact production
implementation (Task 2.1, still blocked on this gate). The two are allowed
to differ; only the eventual Stage 2/live core needs bit-identical math.

Known Stage-1-only simplifications (all conservative or clearly scoped, none
silent):
- **Trade-order tie-break**: if a trade's forward window touches both the
  stop and the target, the stop is assumed to have hit first. Stage 2's
  event-driven engine resolves true bar-by-bar ordering; this screen can't
  cheaply do so and takes the pessimistic side instead of guessing optimistically.
- **Position sequencing**: once a trade is taken, no new entry is considered
  until its full max-hold window has elapsed, even if the real trade would
  have exited (and freed capacity) sooner. Conservative — this can only
  under-count trades, never over-count them.
- **Bracket mode's hold window** is capped at `4 * bollinger.period` bars
  (a self-scaling stand-in for "no time limit" — Stage 2 imposes no such
  cap). `mean_revert` mode uses its own configured `time_stop_s` exactly.
- **Funding is not modeled.** Task 0.1 ingested price candles, not funding
  rate history, so there is no real funding series to apply yet. Expected
  small for short mean-reversion holds, but this is a real, tracked gap —
  Stage 2 must ingest real funding history before funding is modeled honestly.
- **Exit fee assumption**: a target/take-profit exit is costed as a maker
  fill (resting limit, matching PLAN.md's native-bracket design); a stop-loss
  or time-stop exit is costed as a taker flatten (`costs.stop_exit_cost`,
  which already includes the slippage haircut).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import cast

import numpy as np
import polars as pl

from scalpbot.backtest.costs import CostParams, entry_cost, stop_exit_cost
from scalpbot.backtest.research_ledger import append_row
from scalpbot.core.strategy import StrategyConfig

_EMPTY_TRADES_SCHEMA = {"direction": pl.Int64, "r_net": pl.Float64}

_TIMEFRAME_SECONDS = {"1s": 1, "1m": 60, "5m": 300, "1h": 3600}


def _bar_seconds(timeframe: str) -> int:
    """Seconds per bar for `config.timeframe` — needed to convert
    `mean_revert`'s `time_stop_s` into a bar count. `bracket` mode's
    `4 * bollinger.period` hold cap is already expressed in bars, so it
    needs no such conversion and stays resolution-agnostic."""
    return _TIMEFRAME_SECONDS[timeframe]


def _forward_rolling_max(column: str, window: int) -> pl.Expr:
    """Max of `column` over the next `window` bars (excludes the current bar)."""
    return (
        pl.col(column).shift(-1).reverse().rolling_max(window_size=window, min_samples=1).reverse()
    )


def _forward_rolling_min(column: str, window: int) -> pl.Expr:
    """Min of `column` over the next `window` bars (excludes the current bar)."""
    return (
        pl.col(column).shift(-1).reverse().rolling_min(window_size=window, min_samples=1).reverse()
    )


def _compute_indicators(
    df: pl.DataFrame, period: int, sigma: float, rsi_period: int, source_column: str = "close"
) -> pl.DataFrame:
    """Rolling Bollinger bands + Wilder-style RSI over `source_column`, added
    as new columns — plus `signal_value`, a copy of `source_column` under a
    canonical name so `_evaluate_config` never needs to know what it's called.

    `source_column` defaults to `"close"` (price-based signals, the only mode
    used through the mean-reversion/momentum rounds). Passing a different
    column — e.g. a cross-venue basis series — lets the *same* Bollinger/RSI
    entry logic screen a structurally different hypothesis (basis convergence
    instead of price convergence) while trade P&L still realizes against the
    frame's `close` (the actually-tradeable instrument's price), which this
    function never touches. See `backtest/basis_signal.py`.

    Shared across every config with the same `(period, sigma, rsi_period)`
    triple regardless of thresholds/exit mode — `screen_grid` caches this per
    triple so a 108-config grid only pays for the ~18 distinct indicator
    computations it actually needs, not 108.
    """
    source = pl.col(source_column)
    delta = source.diff()
    gain = delta.clip(lower_bound=0.0)
    loss = (-delta).clip(lower_bound=0.0)
    alpha = 1.0 / rsi_period
    avg_gain = gain.ewm_mean(alpha=alpha, adjust=False, min_samples=rsi_period)
    avg_loss = loss.ewm_mean(alpha=alpha, adjust=False, min_samples=rsi_period)
    rs = avg_gain / avg_loss
    rsi = pl.when(avg_loss == 0.0).then(100.0).otherwise(100.0 - 100.0 / (1.0 + rs))

    middle = source.rolling_mean(window_size=period, min_samples=period)
    std = source.rolling_std(window_size=period, min_samples=period, ddof=0)

    return df.with_columns(
        signal_value=source,
        middle_band=middle,
        upper_band=middle + sigma * std,
        lower_band=middle - sigma * std,
        rsi=rsi,
    )


def _evaluate_config(
    indicators: pl.DataFrame, config: StrategyConfig, cost_params: CostParams
) -> pl.DataFrame:
    """Runs one config's entries/exits against pre-computed indicator columns.

    Returns a `direction, r_net` frame, one row per accepted trade (see
    module docstring for the sequencing/tie-break simplifications).
    """
    mode = config.exits["mode"]
    stop_pct = config.exits["stop_pct"] / 100.0
    if mode == "bracket":
        tp_pct: float | None = config.exits["take_profit_pct"] / 100.0
        max_hold_bars = max(4 * config.bollinger.period, 1)
    else:
        tp_pct = None
        max_hold_bars = max(int(config.exits["time_stop_s"]) // _bar_seconds(config.timeframe), 1)

    oversold = config.rsi.oversold
    overbought = config.rsi.overbought

    long_tp_expr = (pl.col("close") * (1 + tp_pct)) if tp_pct is not None else pl.col("middle_band")
    short_tp_expr = (
        (pl.col("close") * (1 - tp_pct)) if tp_pct is not None else pl.col("middle_band")
    )

    # Signal detection compares `signal_value` (the series indicators were
    # computed from — price by default, or e.g. a basis series) against its
    # own bands; entry/exit *prices* below always reference `close` (the
    # actually-tradeable instrument), which stays untouched by source_column.
    #
    # mean_revert: bet the band-pierce reverts (long on lower-band pierce + oversold,
    # betting on a bounce). momentum: bet it continues (long on *upper*-band pierce +
    # overbought, confirming strength rather than exhaustion) — the mirror image.
    if config.signal_direction == "momentum":
        long_signal_expr = (pl.col("signal_value") > pl.col("upper_band")) & (
            pl.col("rsi") >= overbought
        )
        short_signal_expr = (pl.col("signal_value") < pl.col("lower_band")) & (
            pl.col("rsi") <= oversold
        )
    else:
        long_signal_expr = (pl.col("signal_value") < pl.col("lower_band")) & (
            pl.col("rsi") <= oversold
        )
        short_signal_expr = (pl.col("signal_value") > pl.col("upper_band")) & (
            pl.col("rsi") >= overbought
        )

    augmented = indicators.with_row_index("row_idx").with_columns(
        long_signal=long_signal_expr,
        short_signal=short_signal_expr,
        fut_max_high=_forward_rolling_max("high", max_hold_bars),
        fut_min_low=_forward_rolling_min("low", max_hold_bars),
        fut_close_end=pl.col("close").shift(-max_hold_bars),
        long_tp_price=long_tp_expr,
        long_sl_price=pl.col("close") * (1 - stop_pct),
        short_tp_price=short_tp_expr,
        short_sl_price=pl.col("close") * (1 + stop_pct),
    )

    candidates = augmented.filter(pl.col("long_signal") | pl.col("short_signal")).select(
        "row_idx",
        "long_signal",
        "close",
        "fut_max_high",
        "fut_min_low",
        "fut_close_end",
        "long_tp_price",
        "long_sl_price",
        "short_tp_price",
        "short_sl_price",
    )

    if candidates.height == 0:
        return pl.DataFrame(schema=_EMPTY_TRADES_SCHEMA)

    maker_fee_frac = entry_cost(1.0, cost_params)
    taker_exit_frac = stop_exit_cost(1.0, cost_params)

    # Plain numpy arrays instead of `iter_rows(named=True)`: the latter allocates a
    # Python dict per row, which dominates runtime for loose-threshold configs with
    # large candidate counts. Same exact algorithm below, just faster access — this
    # loop is still inherently sequential (each accept/skip decision depends on the
    # previous one via `next_available`), so it can't be vectorized away entirely.
    row_idx = candidates["row_idx"].to_numpy()
    long_signal = candidates["long_signal"].to_numpy()
    close = candidates["close"].to_numpy()
    fut_max_high = candidates["fut_max_high"].to_numpy()
    fut_min_low = candidates["fut_min_low"].to_numpy()
    fut_close_end = candidates["fut_close_end"].to_numpy()
    long_tp_price = candidates["long_tp_price"].to_numpy()
    long_sl_price = candidates["long_sl_price"].to_numpy()
    short_tp_price = candidates["short_tp_price"].to_numpy()
    short_sl_price = candidates["short_sl_price"].to_numpy()

    directions: list[int] = []
    r_nets: list[float] = []
    next_available = -1
    for i in range(len(row_idx)):
        idx = int(row_idx[i])
        if idx <= next_available:
            continue  # a prior trade is still "open" — see sequencing simplification

        is_long = bool(long_signal[i])
        entry_price = close[i]
        fmh, fml = fut_max_high[i], fut_min_low[i]

        if is_long:
            tp_price, sl_price = long_tp_price[i], long_sl_price[i]
            tp_touched = not np.isnan(fmh) and fmh >= tp_price
            sl_touched = not np.isnan(fml) and fml <= sl_price
            direction = 1
        else:
            tp_price, sl_price = short_tp_price[i], short_sl_price[i]
            tp_touched = not np.isnan(fml) and fml <= tp_price
            sl_touched = not np.isnan(fmh) and fmh >= sl_price
            direction = -1

        if sl_touched:
            exit_price, exit_frac = sl_price, taker_exit_frac
        elif tp_touched:
            exit_price, exit_frac = tp_price, maker_fee_frac
        elif not np.isnan(fut_close_end[i]):
            exit_price, exit_frac = fut_close_end[i], taker_exit_frac
        else:
            continue  # trade runs off the end of the corpus — unresolvable, dropped

        raw_return = direction * (exit_price - entry_price) / entry_price
        r_net = raw_return / stop_pct - (maker_fee_frac + exit_frac) / stop_pct

        directions.append(direction)
        r_nets.append(r_net)
        next_available = idx + max_hold_bars

    if not directions:
        return pl.DataFrame(schema=_EMPTY_TRADES_SCHEMA)
    return pl.DataFrame({"direction": directions, "r_net": r_nets})


def _summarize(config: StrategyConfig, symbol: str, trades: pl.DataFrame) -> dict:
    """`standard_error`/`t_stat` make "clearly a real effect" vs. "could be noise"
    legible at a glance now that trial counts are high enough to matter (600+ logged
    so far) — NaN when `n_trades < 2` (undefined sample std), not silently 0, so an
    unresolvable stat is visibly distinct from a genuinely tight one.
    """
    n = trades.height
    if n == 0:
        return {
            "config_name": config.name,
            "symbol": symbol,
            "n_trades": 0,
            "expectancy_r": 0.0,
            "win_rate": 0.0,
            "standard_error": float("nan"),
            "t_stat": float("nan"),
        }
    expectancy_r = cast(float, trades["r_net"].mean())
    win_rate = cast(float, (trades["r_net"] > 0).mean())
    if n < 2:
        standard_error = float("nan")
        t_stat = float("nan")
    else:
        std = cast(float, trades["r_net"].std(ddof=1))
        standard_error = std / (n**0.5)
        t_stat = expectancy_r / standard_error if standard_error > 0 else float("nan")
    return {
        "config_name": config.name,
        "symbol": symbol,
        "n_trades": n,
        "expectancy_r": expectancy_r,
        "win_rate": win_rate,
        "standard_error": standard_error,
        "t_stat": t_stat,
    }


def screen_grid(
    corpus: pl.LazyFrame | pl.DataFrame,
    symbol: str,
    configs: Sequence[StrategyConfig],
    cost_params: CostParams,
    ledger_path: Path | str,
    *,
    data_range: str = "",
    source_column: str = "close",
) -> pl.DataFrame:
    """Evaluates every config in `configs` against one symbol's OHLCV corpus.

    `source_column` selects what indicators are computed from — `"close"`
    (the default) for price-based signals, or another column (e.g. a basis
    series already present in `corpus`) for a structurally different
    hypothesis. Trade P&L always realizes against `corpus`'s `close` column
    regardless — see `_compute_indicators`.

    `corpus` must already have the holdout window excluded and be sorted by
    `open_time_ms` — this function does not know about holdout quarantine or
    the data layer, it only consumes rows. Returns one row per config
    (`config_name, symbol, n_trades, expectancy_r, win_rate`), and appends
    every evaluated config to the research ledger, no exceptions — a config
    that produces zero trades still gets logged as a 0-trade result.

    `configs` should be grouped so every config sharing a
    `(bollinger.period, bollinger.sigma, rsi.period)` triple is contiguous —
    true by construction for `screen_config.iter_configs`'s `product()`
    ordering (period/sigma/rsi_period are the outer loop variables). Only the
    single most-recently-computed indicator frame is kept in memory at a
    time: caching *every* distinct triple's full-corpus frame for the whole
    grid (as an earlier version of this function did) exhausted memory once
    the grid grew past a couple dozen triples — a config-sized corpus can be
    tens of millions of rows, and each cached triple adds another full copy.
    Out-of-order `configs` still work, just without the memory win (every
    config recomputes its indicators).
    """
    df = corpus.collect() if isinstance(corpus, pl.LazyFrame) else corpus

    current_key: tuple[int, float, int] | None = None
    current_indicators: pl.DataFrame | None = None
    summaries: list[dict] = []
    for config in configs:
        key = (config.bollinger.period, config.bollinger.sigma, config.rsi.period)
        if key != current_key:
            current_indicators = _compute_indicators(df, *key, source_column=source_column)
            current_key = key
        indicators = current_indicators
        assert indicators is not None

        trades = _evaluate_config(indicators, config, cost_params)
        summary = _summarize(config, symbol, trades)
        summaries.append(summary)

        append_row(
            config=config,
            symbol=symbol,
            data_range=data_range,
            splits="screen (Stage 1, no walk-forward split)",
            expectancy_r=summary["expectancy_r"],
            n_trades=summary["n_trades"],
            ledger_path=ledger_path,
        )

    return pl.DataFrame(summaries)
