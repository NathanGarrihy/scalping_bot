from __future__ import annotations

import polars as pl
import pytest

from scalpbot.backtest.funding_signal import build_funding_corpus

_HOUR_MS = 3_600_000


def test_build_funding_corpus_hand_verified_rolling_pressure() -> None:
    # 5 hours of funding history, rates [0.01, 0.02, 0.01, -0.01, 0.03];
    # trailing_hours=3 -> pressure at hour i = sum(rate[i-2:i+1]).
    funding_history = pl.DataFrame(
        {
            "open_time_ms": [i * _HOUR_MS for i in range(5)],
            "funding_rate": [0.01, 0.02, 0.01, -0.01, 0.03],
        }
    )
    # HL candles only cover hours 2-4 (the tradeable/backtestable window).
    hl_candles = pl.DataFrame(
        {
            "open_time_ms": [2 * _HOUR_MS, 3 * _HOUR_MS, 4 * _HOUR_MS],
            "open": [100.0, 101.0, 99.0],
            "high": [100.0, 101.0, 99.0],
            "low": [100.0, 101.0, 99.0],
            "close": [100.0, 101.0, 99.0],
        }
    )

    corpus = build_funding_corpus(hl_candles, funding_history, trailing_hours=3)

    assert corpus["open_time_ms"].to_list() == [2 * _HOUR_MS, 3 * _HOUR_MS, 4 * _HOUR_MS]
    # hour2: 0.01+0.02+0.01=0.04; hour3: 0.02+0.01-0.01=0.02; hour4: 0.01-0.01+0.03=0.03
    assert corpus["funding_pressure"].to_list() == pytest.approx([0.04, 0.02, 0.03], abs=1e-9)
    # Tradeable price columns pass through unchanged.
    assert corpus["close"].to_list() == [100.0, 101.0, 99.0]


def test_build_funding_corpus_inner_join_drops_non_overlapping_hours() -> None:
    funding_history = pl.DataFrame(
        {
            "open_time_ms": [0, _HOUR_MS, 2 * _HOUR_MS],
            "funding_rate": [0.01, 0.01, 0.01],
        }
    )
    # HL candles only have hour 2 -- hours 0,1 have funding but no tradeable price.
    hl_candles = pl.DataFrame(
        {
            "open_time_ms": [2 * _HOUR_MS],
            "open": [100.0],
            "high": [100.0],
            "low": [100.0],
            "close": [100.0],
        }
    )

    corpus = build_funding_corpus(hl_candles, funding_history, trailing_hours=3)

    assert corpus["open_time_ms"].to_list() == [2 * _HOUR_MS]
    assert corpus.height == 1


def test_build_funding_corpus_floors_funding_jitter_before_joining() -> None:
    # Real Hyperliquid funding timestamps carry a few-to-tens-of-ms jitter
    # (confirmed empirically against the live API — e.g. "...78", "...05"
    # suffixes, never exactly "...00"), while candle timestamps are exact
    # hour boundaries. An exact-equality join silently drops nearly every
    # overlapping hour if funding timestamps aren't floored first — this is
    # the regression test for that real bug (first real screen run against
    # actual data returned 67 rows instead of thousands).
    funding_history = pl.DataFrame(
        {
            "open_time_ms": [78, _HOUR_MS + 50, 2 * _HOUR_MS + 11],
            "funding_rate": [0.01, 0.01, 0.01],
        }
    )
    hl_candles = pl.DataFrame(
        {
            "open_time_ms": [0, _HOUR_MS, 2 * _HOUR_MS],
            "open": [100.0, 101.0, 102.0],
            "high": [100.0, 101.0, 102.0],
            "low": [100.0, 101.0, 102.0],
            "close": [100.0, 101.0, 102.0],
        }
    )

    corpus = build_funding_corpus(hl_candles, funding_history, trailing_hours=3)

    assert corpus.height == 3
    assert corpus["open_time_ms"].to_list() == [0, _HOUR_MS, 2 * _HOUR_MS]


def test_build_funding_corpus_warms_up_before_join_window() -> None:
    # 30 hours of funding history at a constant rate; HL candles only start
    # at hour 25 -- the trailing_hours=24 window is fully warmed up by then
    # using history *before* the candle window, not truncated at its start.
    funding_history = pl.DataFrame(
        {
            "open_time_ms": [i * _HOUR_MS for i in range(30)],
            "funding_rate": [0.001] * 30,
        }
    )
    hl_candles = pl.DataFrame(
        {
            "open_time_ms": [25 * _HOUR_MS],
            "open": [100.0],
            "high": [100.0],
            "low": [100.0],
            "close": [100.0],
        }
    )

    corpus = build_funding_corpus(hl_candles, funding_history, trailing_hours=24)

    assert corpus["funding_pressure"].to_list() == pytest.approx([0.024], abs=1e-9)
