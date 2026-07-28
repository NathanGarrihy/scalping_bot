from __future__ import annotations

import polars as pl
import pytest

from scalpbot.backtest.basis_signal import build_basis_corpus

_HOUR_MS = 3_600_000


def test_build_basis_corpus_hand_verified_basis_bps() -> None:
    # Binance 1s bars across two hourly buckets; bucket-last close = 100, 200.
    binance_1s = pl.DataFrame(
        {
            "open_time_ms": [0, _HOUR_MS - 1000, _HOUR_MS, 2 * _HOUR_MS - 1000],
            "open": [99.0, 100.0, 199.0, 200.0],
            "high": [99.0, 100.0, 199.0, 200.0],
            "low": [99.0, 100.0, 199.0, 200.0],
            "close": [99.0, 100.0, 199.0, 200.0],
            "volume": [1.0, 1.0, 1.0, 1.0],
        }
    )
    # HL's own OHLC at the same two hourly buckets: +10bps and -5bps vs Binance.
    hl_1h = pl.DataFrame(
        {
            "open_time_ms": [0, _HOUR_MS],
            "open": [100.9, 199.5],
            "high": [101.5, 200.0],
            "low": [100.5, 199.0],
            "close": [100.1, 199.9],
        }
    )

    corpus = build_basis_corpus(binance_1s, hl_1h)

    assert corpus["open_time_ms"].to_list() == [0, _HOUR_MS]
    # (100.1-100)/100*10000 = 10bps; (199.9-200)/200*10000 = -5bps
    assert corpus["basis_bps"].to_list() == pytest.approx([10.0, -5.0], abs=1e-6)
    # Tradeable price columns are HL's own OHLC, not Binance's.
    assert corpus["close"].to_list() == [100.1, 199.9]
    assert corpus["high"].to_list() == [101.5, 200.0]


def test_build_basis_corpus_inner_join_drops_non_overlapping_hours() -> None:
    binance_1s = pl.DataFrame(
        {
            "open_time_ms": [0, _HOUR_MS],
            "open": [100.0, 200.0],
            "high": [100.0, 200.0],
            "low": [100.0, 200.0],
            "close": [100.0, 200.0],
            "volume": [1.0, 1.0],
        }
    )
    # HL only has the second hour — the first hour has no HL data to join against.
    hl_1h = pl.DataFrame(
        {
            "open_time_ms": [_HOUR_MS],
            "open": [199.0],
            "high": [200.0],
            "low": [198.0],
            "close": [199.0],
        }
    )

    corpus = build_basis_corpus(binance_1s, hl_1h)

    assert corpus["open_time_ms"].to_list() == [_HOUR_MS]
    assert corpus.height == 1
