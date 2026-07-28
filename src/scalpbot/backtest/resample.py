"""OHLCV resampling for the Stage 1 timeframe/fee-drag experiment (Task 0.3
Phase A.2 — isolates "no edge" from "edge drowned by 1s trade frequency").

Pure polars, no I/O. This is a research-time transform, not part of the data
layer's archival contract (`schema.py`/`paths.py`) — nothing built here is
ever written back to `data/`.
"""

from __future__ import annotations

import polars as pl


def resample_ohlcv(df: pl.DataFrame, bucket_ms: int) -> pl.DataFrame:
    """Groups `df` into `bucket_ms`-wide buckets keyed by
    `open_time_ms // bucket_ms * bucket_ms` (the bucket's start time):
    `open`/`high`/`low`/`close` = first/max/min/last within the bucket,
    `volume` = sum. A bucket with zero source rows simply isn't present in
    the output — matches the data layer's "missing means missing, not zero"
    convention (see `integrity.py`), not forward-filled.
    """
    return (
        df.sort("open_time_ms")
        .with_columns((pl.col("open_time_ms") // bucket_ms * bucket_ms).alias("open_time_ms"))
        .group_by("open_time_ms", maintain_order=True)
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
        )
    )
