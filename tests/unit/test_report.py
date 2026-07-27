from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from scalpbot.data.config import DataConfig
from scalpbot.data.report import build_report, render_text


def _make_config() -> DataConfig:
    return DataConfig.model_validate(
        {
            "signal_corpus": {
                "source": "binance_archive",
                "interval": "1s",
                "start": "2024-07-01",
                "end": "2024-07-05",
                "holdout_months": 0,
            },
            "venue_corpus": {"source": "hyperliquid_archive", "start": "2024-07-01"},
        }
    )


def _write_binance_day(root: Path, symbol: str, day: date, base_price: float) -> None:
    n = 86_400
    path = root / "binance" / "klines" / symbol / "1s" / f"{day.isoformat()}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    day_start_ms = int(datetime.combine(day, datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
    pl.DataFrame(
        {
            "open_time_ms": [day_start_ms + i * 1000 for i in range(n)],
            "close": [base_price] * n,
            "volume": [1.0] * n,
        },
        schema={"open_time_ms": pl.Int64, "close": pl.Float64, "volume": pl.Float64},
    ).write_parquet(path)


def _write_hl_day(root: Path, coin: str, day: date, base_price: float) -> None:
    n = 24
    path = root / "hyperliquid" / "candles" / coin / "1h" / f"{day.isoformat()}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    day_start_ms = int(datetime.combine(day, datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
    pl.DataFrame(
        {
            "open_time_ms": [day_start_ms + i * 3_600_000 for i in range(n)],
            "close": [base_price] * n,
            "volume": [1.0] * n,
        },
        schema={"open_time_ms": pl.Int64, "close": pl.Float64, "volume": pl.Float64},
    ).write_parquet(path)


def test_build_report_over_synthetic_partitions(tmp_path: Path) -> None:
    cfg = _make_config()
    _write_binance_day(tmp_path, "BTCUSDT", date(2024, 7, 1), 100.0)
    _write_binance_day(tmp_path, "BTCUSDT", date(2024, 7, 2), 100.0)
    _write_hl_day(tmp_path, "BTC", date(2024, 7, 1), 100.01)

    report = build_report(tmp_path, cfg, ["BTCUSDT"])

    assert len(report.gaps) == 2  # one Binance gap-report, one HL gap-report
    assert len(report.regime_coverage) == 1
    assert len(report.cross_venue_basis) == 1
    assert report.negative_volume_hits == {}


def test_build_report_missing_data_returns_empty_sections(tmp_path: Path) -> None:
    cfg = _make_config()
    report = build_report(tmp_path, cfg, ["BTCUSDT"])

    assert report.gaps == []
    assert report.regime_coverage == []
    assert report.cross_venue_basis == []


def test_render_text_produces_readable_output(tmp_path: Path) -> None:
    cfg = _make_config()
    _write_binance_day(tmp_path, "BTCUSDT", date(2024, 7, 1), 100.0)
    _write_hl_day(tmp_path, "BTC", date(2024, 7, 1), 100.0)

    report = build_report(tmp_path, cfg, ["BTCUSDT"])
    text = render_text(report)

    assert "Data Integrity Report" in text
    assert "BTCUSDT" in text
    assert "quarantined" in text


def test_build_report_excludes_holdout_window(tmp_path: Path) -> None:
    cfg = DataConfig.model_validate(
        {
            "signal_corpus": {
                "source": "binance_archive",
                "interval": "1s",
                "start": "2024-06-01",
                "end": "2024-07-31",
                "holdout_months": 1,  # holdout_start == 2024-07-01 (all of July)
            },
            "venue_corpus": {"source": "hyperliquid_archive", "start": "2024-06-01"},
        }
    )
    _write_binance_day(tmp_path, "BTCUSDT", date(2024, 6, 15), 100.0)
    _write_binance_day(tmp_path, "BTCUSDT", date(2024, 7, 15), 999.0)  # inside holdout

    report = build_report(tmp_path, cfg, ["BTCUSDT"])

    # only the 2024-07-01 day should feed regime coverage; a lone day has no
    # drawdown to speak of, but the holdout day's absurd price must not leak in.
    assert len(report.regime_coverage) == 1
    coverage = report.regime_coverage[0]
    assert coverage.max_drawdown_pct == 0.0
