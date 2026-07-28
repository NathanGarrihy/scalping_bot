"""Funding-rate-extreme corpus builder (Task 0.3 "zoom out" round, Phase E —
bet that extreme accumulated funding pressure (crowded positioning) precedes
a squeeze back toward flat, a real, well-known perp-market mechanism, not a
price technical).

Reuses `vector_screen.py`'s Bollinger/RSI machinery unchanged via
`source_column="funding_pressure"` — same pattern `basis_signal.py`
established: the *signal* is detected on the funding series, trade P&L
realizes against Hyperliquid's own OHLC.

The rolling `funding_pressure` window is computed over the **full** funding
history (which the "zoom out" round confirmed covers 2024-07-01+, unlike the
depth-limited price candles) before joining down to the candle corpus's
shorter window — so the indicator itself is fully warmed up by the time it
enters the tradeable/backtestable range. This doesn't fix the underlying
sample-size ceiling (still bounded by how much HL *price* history exists),
but it does mean the join isn't wasting any of that short window on
indicator warm-up.
"""

from __future__ import annotations

import polars as pl

_HOUR_MS = 3_600_000


def build_funding_corpus(
    hl_candles: pl.DataFrame, funding_history: pl.DataFrame, *, trailing_hours: int = 24
) -> pl.DataFrame:
    """`hl_candles`: `open_time_ms, open, high, low, close` (the tradeable
    price). `funding_history`: `open_time_ms, funding_rate`. Both nominally
    1h resolution, but **not on the same clock**: candle timestamps are exact
    hour boundaries, funding event timestamps carry a few-to-tens-of-ms
    jitter (confirmed empirically — e.g. `...78`, `...05` suffixes, never
    `...00`). Funding timestamps are floored to the hour before joining, or
    an exact-equality join silently drops the vast majority of otherwise-
    overlapping hours. Returns `open_time_ms, open, high, low, close,
    funding_pressure` — inner-joined, so only hours with both a tradeable
    price and known funding contribute rows.
    """
    funding_pressure = (
        funding_history.with_columns(
            (pl.col("open_time_ms") // _HOUR_MS * _HOUR_MS).alias("open_time_ms")
        )
        .sort("open_time_ms")
        .with_columns(
            pl.col("funding_rate")
            .rolling_sum(window_size=trailing_hours, min_samples=trailing_hours)
            .alias("funding_pressure")
        )
    )

    joined = hl_candles.select("open_time_ms", "open", "high", "low", "close").join(
        funding_pressure.select("open_time_ms", "funding_pressure"), on="open_time_ms", how="inner"
    )
    return joined.sort("open_time_ms")
