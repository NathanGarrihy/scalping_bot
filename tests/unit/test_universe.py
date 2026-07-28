from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from scalpbot.data.universe import (
    UniverseSettingsConfig,
    aggregate_daily_quote_volume,
    compute_universe,
    monthly_rebalance_dates,
    write_universe_file,
)

_MS_PER_DAY = 86_400_000


def _day_ms(d: date) -> int:
    return (d - date(1970, 1, 1)).days * _MS_PER_DAY


def test_monthly_rebalance_dates_spans_full_months() -> None:
    dates = monthly_rebalance_dates(date(2024, 7, 1), date(2024, 9, 30))
    assert dates == [date(2024, 7, 1), date(2024, 8, 1), date(2024, 9, 1)]


def test_monthly_rebalance_dates_excludes_month_starting_after_end() -> None:
    dates = monthly_rebalance_dates(date(2024, 7, 15), date(2024, 8, 10))
    # 2024-07-01 is before start, so excluded; 2024-08-01 is within range.
    assert dates == [date(2024, 8, 1)]


def test_aggregate_daily_quote_volume_hand_verified() -> None:
    klines = pl.DataFrame(
        {
            "open_time_ms": [0, 500_000, _MS_PER_DAY, _MS_PER_DAY + 1000],
            "quote_volume": [100.0, 50.0, 10.0, 5.0],
        }
    )
    result = aggregate_daily_quote_volume(klines, "BTCUSDT")
    assert result["date_ms"].to_list() == [0, _MS_PER_DAY]
    assert result["quote_volume"].to_list() == [150.0, 15.0]
    assert result["symbol"].to_list() == ["BTCUSDT", "BTCUSDT"]


def test_compute_universe_ranks_by_trailing_volume_no_lookahead() -> None:
    # Two symbols, 60 days of daily volume. HIGH has consistently higher
    # volume through day 40, then LOW overtakes it for the remaining days.
    # The 2024-09-01 rebalance's trailing 30-day window is entirely within
    # the "HIGH wins" period; the 2024-10-01 rebalance's window should catch
    # the switch to "LOW wins" — this is the no-lookahead property under test.
    start = date(2024, 8, 1)
    rows = []
    for i in range(75):
        d = date(2024, 8, 1)
        day_ms = _day_ms(d) + i * _MS_PER_DAY
        # HIGH: volume decays after day 45; LOW: volume ramps up after day 45.
        high_vol = 1000.0 if i < 45 else 10.0
        low_vol = 10.0 if i < 45 else 1000.0
        rows.append({"date_ms": day_ms, "symbol": "HIGH", "quote_volume": high_vol})
        rows.append({"date_ms": day_ms, "symbol": "LOW", "quote_volume": low_vol})
    daily_volume = pl.DataFrame(rows)

    cfg = UniverseSettingsConfig(
        volume_rank_max=1, spread_bps_max=4.0, listing_age_days_min=0, rebalance="monthly"
    )
    memberships = compute_universe(daily_volume, cfg, start, date(2024, 10, 15), trailing_days=30)

    by_date_symbol = {(m.rebalance_date, m.symbol): m.in_universe for m in memberships}

    # 2024-09-01: trailing 30 days (Aug 2 - Aug 31) are entirely in the
    # "HIGH wins" period -> HIGH ranked #1, in universe; LOW excluded.
    assert by_date_symbol[(date(2024, 9, 1), "HIGH")] is True
    assert by_date_symbol[(date(2024, 9, 1), "LOW")] is False

    # 2024-10-01: trailing 30 days (Sep 1 - Sep 30) are entirely after the
    # day-45 switch (day 45 = Sep 14) -> LOW now ranked #1.
    assert by_date_symbol[(date(2024, 10, 1), "LOW")] is True
    assert by_date_symbol[(date(2024, 10, 1), "HIGH")] is False


def test_compute_universe_enforces_listing_age_floor() -> None:
    start = date(2024, 8, 1)
    rows = []
    for i in range(60):
        day_ms = _day_ms(start) + i * _MS_PER_DAY
        rows.append({"date_ms": day_ms, "symbol": "OLD", "quote_volume": 500.0})
    # NEW only starts trading on day 55 (2024-09-25) — well within the
    # trailing window by the Oct 1 rebalance, but far short of a 90-day
    # listing-age floor.
    for i in range(55, 60):
        day_ms = _day_ms(start) + i * _MS_PER_DAY
        rows.append({"date_ms": day_ms, "symbol": "NEW", "quote_volume": 10_000.0})
    daily_volume = pl.DataFrame(rows)

    cfg = UniverseSettingsConfig(
        volume_rank_max=5, spread_bps_max=4.0, listing_age_days_min=90, rebalance="monthly"
    )
    memberships = compute_universe(daily_volume, cfg, start, date(2024, 10, 1), trailing_days=30)

    new_oct = next(
        m for m in memberships if m.symbol == "NEW" and m.rebalance_date == date(2024, 10, 1)
    )
    # NEW has by far the higher trailing volume (would rank #1 on volume
    # alone) but fails the 90-day listing-age floor -> excluded regardless.
    assert new_oct.rank == 1
    assert new_oct.in_universe is False


def test_write_universe_file_round_trips(tmp_path: Path) -> None:
    from scalpbot.data.universe import UniverseMembership

    memberships = [
        UniverseMembership(
            rebalance_date=date(2024, 9, 1), symbol="BTCUSDT", rank=1, in_universe=True
        ),
        UniverseMembership(
            rebalance_date=date(2024, 9, 1), symbol="DOGEUSDT", rank=41, in_universe=False
        ),
    ]
    out_path = tmp_path / "universe.parquet"

    write_universe_file(memberships, out_path)

    result = pl.read_parquet(out_path)
    assert result["symbol"].to_list() == ["BTCUSDT", "DOGEUSDT"]
    assert result["in_universe"].to_list() == [True, False]


def test_load_universe_config_parses_real_research_yaml() -> None:
    from scalpbot.data.universe import load_universe_config

    cfg = load_universe_config("configs/research.yaml")
    assert cfg.volume_rank_max == 40
    assert cfg.listing_age_days_min == 90
    assert cfg.rebalance == "monthly"
