from __future__ import annotations

import polars as pl
import pytest

from scalpbot.data.integrity import (
    check_monotonic_and_gaps,
    check_non_negative_volume,
    compute_cross_venue_basis,
    compute_regime_coverage,
)

ONE_SEC_MS = 1000
ONE_HOUR_MS = 3_600_000


def _clean_series(n: int, start_ms: int = 0, step_ms: int = ONE_SEC_MS) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "open_time_ms": [start_ms + i * step_ms for i in range(n)],
            "close": [100.0 + 0.01 * i for i in range(n)],
            "volume": [1.0] * n,
        }
    )


def test_check_monotonic_and_gaps_clean_series_has_no_gaps() -> None:
    df = _clean_series(100)
    report = check_monotonic_and_gaps(df, interval_ms=ONE_SEC_MS, symbol="BTCUSDT")
    assert report.n_gaps == 0
    assert report.max_gap_ms == 0
    assert report.gap_starts == []


def test_check_monotonic_and_gaps_detects_injected_gap() -> None:
    df = _clean_series(10)
    # remove rows 4 and 5 to inject a gap of 3s where 1s was expected
    df = df.filter(~pl.col("open_time_ms").is_in([4000, 5000]))
    report = check_monotonic_and_gaps(df, interval_ms=ONE_SEC_MS, symbol="BTCUSDT")
    assert report.n_gaps == 1
    assert report.max_gap_ms == 3000
    assert report.gap_starts == [3000]


def test_check_monotonic_and_gaps_raises_on_duplicate_timestamp() -> None:
    df = pl.DataFrame(
        {
            "open_time_ms": [0, 1000, 1000, 2000],
            "close": [100.0, 100.0, 100.0, 100.0],
            "volume": [1.0, 1.0, 1.0, 1.0],
        }
    )
    with pytest.raises(ValueError, match="duplicate"):
        check_monotonic_and_gaps(df, interval_ms=ONE_SEC_MS, symbol="BTCUSDT")


def test_check_non_negative_volume_flags_negative_rows() -> None:
    df = pl.DataFrame(
        {
            "open_time_ms": [0, 1000, 2000],
            "volume": [1.0, -0.5, 2.0],
        }
    )
    assert check_non_negative_volume(df) == [1000]


def test_check_non_negative_volume_empty_when_all_non_negative() -> None:
    df = _clean_series(5)
    assert check_non_negative_volume(df) == []


def test_compute_regime_coverage_detects_drawdown_and_recovery() -> None:
    # peak at day 0 (close=100), trough at day 5 (close=55 -> 45% drawdown), partial recovery
    closes = [100.0, 90.0, 80.0, 70.0, 60.0, 55.0, 65.0, 75.0]
    df = pl.DataFrame(
        {
            "open_time_ms": [i * 86_400_000 for i in range(len(closes))],
            "close": closes,
        }
    )
    coverage = compute_regime_coverage(df, symbol="BTCUSDT", drawdown_threshold_pct=40.0)

    assert coverage.max_drawdown_pct == pytest.approx(45.0)
    assert coverage.meets_drawdown_threshold is True
    assert coverage.max_drawdown_window == (0, 5 * 86_400_000)


def test_compute_regime_coverage_below_threshold_reports_false() -> None:
    closes = [100.0, 98.0, 96.0, 95.0]
    df = pl.DataFrame(
        {
            "open_time_ms": [i * 86_400_000 for i in range(len(closes))],
            "close": closes,
        }
    )
    coverage = compute_regime_coverage(df, symbol="BTCUSDT", drawdown_threshold_pct=40.0)
    assert coverage.meets_drawdown_threshold is False


def test_compute_regime_coverage_classifies_chop_and_trend_days() -> None:
    # day0->day1 flat (chop), day1->day2 big move (trend)
    closes = [100.0, 100.5, 110.0]
    df = pl.DataFrame(
        {
            "open_time_ms": [i * 86_400_000 for i in range(len(closes))],
            "close": closes,
        }
    )
    coverage = compute_regime_coverage(df, symbol="BTCUSDT")
    assert coverage.chop_days == 1
    assert coverage.trend_days == 1


def test_compute_cross_venue_basis_hand_computed_value() -> None:
    # Binance 1s bars at two hourly buckets; HL 1h bars aligned to the same buckets.
    binance_df = pl.DataFrame(
        {
            "open_time_ms": [0, ONE_HOUR_MS - 1000, ONE_HOUR_MS, 2 * ONE_HOUR_MS - 1000],
            "close": [100.0, 101.0, 200.0, 202.0],
        }
    )
    hl_df = pl.DataFrame(
        {
            "open_time_ms": [0, ONE_HOUR_MS],
            "close": [101.101, 202.202],  # +10 bps vs binance's bucket-last close (101, 202)
        }
    )

    basis = compute_cross_venue_basis(
        binance_df,
        hl_df,
        binance_symbol="BTCUSDT",
        hl_symbol="BTC",
        hl_interval_ms=ONE_HOUR_MS,
    )

    assert basis.n_overlapping_bars == 2
    assert basis.mean_basis_bps == pytest.approx(10.0, abs=0.01)
    assert basis.max_abs_basis_bps == pytest.approx(10.0, abs=0.01)


def test_compute_cross_venue_basis_no_overlap_returns_zeroed_report() -> None:
    binance_df = pl.DataFrame({"open_time_ms": [0], "close": [100.0]})
    hl_df = pl.DataFrame({"open_time_ms": [10 * ONE_HOUR_MS], "close": [100.0]})

    basis = compute_cross_venue_basis(
        binance_df,
        hl_df,
        binance_symbol="BTCUSDT",
        hl_symbol="BTC",
        hl_interval_ms=ONE_HOUR_MS,
    )

    assert basis.n_overlapping_bars == 0
    assert basis.mean_basis_bps == 0.0
