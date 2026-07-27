from __future__ import annotations

from scalpbot.data.schema import (
    BINANCE_KLINE_SCHEMA,
    HYPERLIQUID_CANDLE_SCHEMA,
    empty_frame,
)


def test_binance_kline_schema_has_expected_columns() -> None:
    assert set(BINANCE_KLINE_SCHEMA) == {
        "symbol",
        "open_time_ms",
        "close_time_ms",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "n_trades",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "source",
    }


def test_hyperliquid_candle_schema_has_expected_columns() -> None:
    assert set(HYPERLIQUID_CANDLE_SCHEMA) == {
        "symbol",
        "interval",
        "open_time_ms",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "n_trades",
        "source",
    }


def test_empty_frame_constructs_with_zero_rows() -> None:
    frame = empty_frame(BINANCE_KLINE_SCHEMA)
    assert frame.height == 0
    assert set(frame.columns) == set(BINANCE_KLINE_SCHEMA)


def test_empty_frame_works_for_hyperliquid_schema_too() -> None:
    frame = empty_frame(HYPERLIQUID_CANDLE_SCHEMA)
    assert frame.height == 0
    assert set(frame.columns) == set(HYPERLIQUID_CANDLE_SCHEMA)
