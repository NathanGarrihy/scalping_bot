from __future__ import annotations

import polars as pl

from scalpbot.backtest.resample import resample_ohlcv


def test_resample_ohlcv_hand_verified_two_buckets() -> None:
    # 6 one-second bars: bars 0-2 fall in bucket [0, 3000), bars 3-5 in
    # bucket [3000, 6000) with a 3000ms bucket width.
    df = pl.DataFrame(
        {
            "open_time_ms": [0, 1000, 2000, 3000, 4000, 5000],
            "open": [10.0, 11.0, 9.0, 20.0, 21.0, 19.0],
            "high": [12.0, 13.0, 10.0, 22.0, 23.0, 20.0],
            "low": [9.0, 10.0, 8.0, 19.0, 20.0, 18.0],
            "close": [11.0, 9.0, 10.0, 21.0, 19.0, 20.0],
            "volume": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )

    result = resample_ohlcv(df, bucket_ms=3000)

    assert result["open_time_ms"].to_list() == [0, 3000]
    assert result["open"].to_list() == [10.0, 20.0]  # first of each bucket
    assert result["high"].to_list() == [13.0, 23.0]  # max of each bucket
    assert result["low"].to_list() == [8.0, 18.0]  # min of each bucket
    assert result["close"].to_list() == [10.0, 20.0]  # last of each bucket
    assert result["volume"].to_list() == [6.0, 15.0]  # sum of each bucket


def test_resample_ohlcv_missing_bucket_is_absent_not_zero() -> None:
    # bars at t=0 and t=6000 with nothing in between -> the middle bucket
    # [3000, 6000) has zero source rows and must not appear in the output.
    df = pl.DataFrame(
        {
            "open_time_ms": [0, 6000],
            "open": [10.0, 20.0],
            "high": [10.0, 20.0],
            "low": [10.0, 20.0],
            "close": [10.0, 20.0],
            "volume": [1.0, 1.0],
        }
    )

    result = resample_ohlcv(df, bucket_ms=3000)

    assert result["open_time_ms"].to_list() == [0, 6000]
    assert result.height == 2


def test_resample_ohlcv_unsorted_input_sorted_correctly() -> None:
    df = pl.DataFrame(
        {
            "open_time_ms": [2000, 0, 1000],
            "open": [3.0, 1.0, 2.0],
            "high": [3.0, 1.0, 2.0],
            "low": [3.0, 1.0, 2.0],
            "close": [3.0, 1.0, 2.0],
            "volume": [1.0, 1.0, 1.0],
        }
    )

    result = resample_ohlcv(df, bucket_ms=3000)

    assert result["open_time_ms"].to_list() == [0]
    assert result["open"].to_list() == [1.0]  # first by time, not by input order
    assert result["close"].to_list() == [3.0]  # last by time
