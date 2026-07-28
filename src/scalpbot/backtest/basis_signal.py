"""Cross-venue basis-dislocation corpus builder (Task 0.3 "zoom out" round,
Phase D — a structurally different hypothesis from price-oscillator
mean-reversion/momentum: bet the Binance/Hyperliquid price *basis* reverts,
not that either venue's own price does. Economically closer to arbitrage
than prediction — a real convergence mechanism, not just a statistical
pattern in one series.

Reuses `vector_screen.py`'s Bollinger/RSI machinery unchanged via
`source_column="basis_bps"`: the *signal* is detected on the basis series,
but trade P&L realizes against Hyperliquid's own OHLC (the actually-tradeable
instrument on this venue) — see `vector_screen._compute_indicators`.

**Sample-size caveat, stated up front**: the Hyperliquid corpus only covers
`venue_corpus.start` (2026-01-01) onward — about 90 days pre-holdout, at 1h
resolution. That's at most ~2,160 hourly bars, an order of magnitude smaller
than the price-based rounds' tens of millions of 1s rows. Results here need
wider error bars, not the same confidence as the earlier rounds — flagged
explicitly so a favorable-looking small sample doesn't get over-read.
"""

from __future__ import annotations

import polars as pl

from scalpbot.backtest.resample import resample_ohlcv

_HL_INTERVAL_MS = 3_600_000
_BPS = 10_000


def build_basis_corpus(binance_1s: pl.DataFrame, hl_1h: pl.DataFrame) -> pl.DataFrame:
    """Resamples `binance_1s` (1s OHLCV, `open_time_ms/open/high/low/close`)
    down to Hyperliquid's native 1h resolution, inner-joins against `hl_1h`
    (already at 1h, same columns) on `open_time_ms`, and computes
    `basis_bps = (hl_close - binance_close) / binance_close * 10000`.

    Output columns are `open_time_ms, open, high, low, close, basis_bps`
    where `open/high/low/close` are **Hyperliquid's own OHLC** — the
    tradeable instrument — not Binance's. `basis_bps` is the signal series
    consumed via `vector_screen.screen_grid(..., source_column="basis_bps")`.
    """
    binance_1h = resample_ohlcv(binance_1s, _HL_INTERVAL_MS)

    joined = binance_1h.select("open_time_ms", pl.col("close").alias("binance_close")).join(
        hl_1h.select("open_time_ms", "open", "high", "low", "close"),
        on="open_time_ms",
        how="inner",
    )

    return joined.with_columns(
        ((pl.col("close") - pl.col("binance_close")) / pl.col("binance_close") * _BPS).alias(
            "basis_bps"
        )
    ).select("open_time_ms", "open", "high", "low", "close", "basis_bps")
