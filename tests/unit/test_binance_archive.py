from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import httpx
import polars as pl
import pytest

from scalpbot.data.binance_archive import (
    archive_url,
    fetch_day_zip,
    ingest_symbol_range,
    parse_aggtrade_zip,
    resample_to_1s_bars,
)

FIXTURES = Path(__file__).parent / "fixtures" / "data"
DAY_START_MS = 1719792000000  # 2024-07-01T00:00:00Z


def test_archive_url_format() -> None:
    url = archive_url("BTCUSDT", date(2024, 7, 1))
    assert url == (
        "https://data.binance.vision/data/futures/um/daily/aggTrades/"
        "BTCUSDT/BTCUSDT-aggTrades-2024-07-01.zip"
    )


def test_parse_aggtrade_zip_matches_expected_shape() -> None:
    raw = (FIXTURES / "binance_sample_aggtrades.zip").read_bytes()
    ticks = parse_aggtrade_zip(raw, "BTCUSDT")

    assert ticks.height == 5
    assert ticks["transact_time_ms"].is_sorted()
    assert ticks["is_buyer_maker"].dtype == pl.Boolean


def test_parse_aggtrade_zip_rejects_multi_member_zip(tmp_path: Path) -> None:
    bad_zip = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("a.csv", "1,2\n")
        zf.writestr("b.csv", "3,4\n")

    with pytest.raises(ValueError, match="exactly one CSV member"):
        parse_aggtrade_zip(bad_zip.read_bytes(), "BTCUSDT")


def _bar_at_second(frame: pl.DataFrame, second: int) -> dict:
    row = frame.filter(pl.col("open_time_ms") == DAY_START_MS + second * 1000)
    assert row.height == 1
    return row.to_dicts()[0]


def test_resample_to_1s_bars_produces_full_day() -> None:
    raw = (FIXTURES / "binance_sample_aggtrades.zip").read_bytes()
    ticks = parse_aggtrade_zip(raw, "BTCUSDT")
    frame = resample_to_1s_bars(ticks, "BTCUSDT", date(2024, 7, 1))

    assert frame.height == 86_400
    assert frame["open_time_ms"].is_sorted()
    assert frame["symbol"].unique().to_list() == ["BTCUSDT"]
    assert frame["source"].unique().to_list() == ["binance_archive"]


def test_resample_to_1s_bars_aggregates_multi_trade_second() -> None:
    raw = (FIXTURES / "binance_sample_aggtrades.zip").read_bytes()
    ticks = parse_aggtrade_zip(raw, "BTCUSDT")
    frame = resample_to_1s_bars(ticks, "BTCUSDT", date(2024, 7, 1))

    bar = _bar_at_second(frame, 0)
    assert bar["open"] == pytest.approx(63000.0)
    assert bar["close"] == pytest.approx(63001.0)
    assert bar["high"] == pytest.approx(63001.0)
    assert bar["low"] == pytest.approx(63000.0)
    assert bar["volume"] == pytest.approx(0.8)
    assert bar["quote_volume"] == pytest.approx(50400.3)
    assert bar["n_trades"] == 2
    assert bar["taker_buy_base_volume"] == pytest.approx(0.5)
    assert bar["taker_buy_quote_volume"] == pytest.approx(31500.0)


def test_resample_to_1s_bars_forward_fills_empty_second() -> None:
    raw = (FIXTURES / "binance_sample_aggtrades.zip").read_bytes()
    ticks = parse_aggtrade_zip(raw, "BTCUSDT")
    frame = resample_to_1s_bars(ticks, "BTCUSDT", date(2024, 7, 1))

    prior_close = _bar_at_second(frame, 2)["close"]
    empty_bar = _bar_at_second(frame, 3)  # no trades landed in this second

    assert empty_bar["open"] == pytest.approx(prior_close)
    assert empty_bar["high"] == pytest.approx(prior_close)
    assert empty_bar["low"] == pytest.approx(prior_close)
    assert empty_bar["close"] == pytest.approx(prior_close)
    assert empty_bar["volume"] == pytest.approx(0.0)
    assert empty_bar["n_trades"] == 0


def test_resample_to_1s_bars_trailing_seconds_forward_fill_last_close() -> None:
    raw = (FIXTURES / "binance_sample_aggtrades.zip").read_bytes()
    ticks = parse_aggtrade_zip(raw, "BTCUSDT")
    frame = resample_to_1s_bars(ticks, "BTCUSDT", date(2024, 7, 1))

    last_trade_close = _bar_at_second(frame, 4)["close"]
    tail_bar = _bar_at_second(frame, 86_399)

    assert tail_bar["close"] == pytest.approx(last_trade_close)
    assert tail_bar["volume"] == pytest.approx(0.0)


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_day_zip_returns_bytes_on_200() -> None:
    body = (FIXTURES / "binance_sample_aggtrades.zip").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with _mock_transport(handler) as client:
        result = fetch_day_zip("BTCUSDT", date(2024, 7, 1), client=client)

    assert result == body


def test_fetch_day_zip_returns_none_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with _mock_transport(handler) as client:
        result = fetch_day_zip("DOGEUSDT", date(2020, 1, 1), client=client)

    assert result is None


def test_fetch_day_zip_retries_then_raises_on_persistent_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scalpbot.data.binance_archive.time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    with _mock_transport(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_day_zip("BTCUSDT", date(2024, 7, 1), client=client, max_retries=2)

    assert calls["n"] == 3  # initial attempt + 2 retries


def test_ingest_symbol_range_writes_partitions_and_summarizes(tmp_path: Path) -> None:
    body = (FIXTURES / "binance_sample_aggtrades.zip").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if "2024-07-02" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, content=body)

    with _mock_transport(handler) as client:
        summary = ingest_symbol_range(
            "BTCUSDT",
            date(2024, 7, 1),
            date(2024, 7, 3),
            data_root=tmp_path,
            client=client,
        )

    assert summary.days_total == 3
    assert summary.days_fetched == 2
    assert summary.days_skipped_not_listed == 1
    assert summary.days_failed == 0
    assert summary.first_available_day == date(2024, 7, 1)

    written = tmp_path / "binance" / "klines" / "BTCUSDT" / "1s" / "2024-07-01.parquet"
    assert written.exists()
    assert pl.read_parquet(written).height == 86_400


def test_ingest_symbol_range_skips_already_complete_partition(tmp_path: Path) -> None:
    from scalpbot.data.paths import partition_path

    final_path = partition_path(tmp_path, "binance", "klines", "BTCUSDT", "1s", date(2024, 7, 1))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"open_time_ms": list(range(86_400))}).write_parquet(final_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not fetch an already-complete partition")

    with _mock_transport(handler) as client:
        summary = ingest_symbol_range(
            "BTCUSDT",
            date(2024, 7, 1),
            date(2024, 7, 1),
            data_root=tmp_path,
            client=client,
        )

    assert summary.days_skipped_existing == 1
    assert summary.days_fetched == 0


def test_ingest_symbol_range_records_persistent_failure_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scalpbot.data.binance_archive.time.sleep", lambda _seconds: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with _mock_transport(handler) as client:
        summary = ingest_symbol_range(
            "BTCUSDT",
            date(2024, 7, 1),
            date(2024, 7, 2),
            data_root=tmp_path,
            client=client,
        )

    assert summary.days_failed == 2
    assert summary.failed_days == [date(2024, 7, 1), date(2024, 7, 2)]
