from __future__ import annotations

import json
from datetime import UTC, date
from pathlib import Path

import httpx
import polars as pl
import pytest

from scalpbot.data.hyperliquid_funding import (
    OUTPUT_INTERVAL,
    fetch_day_funding,
    funding_history_request,
    ingest_symbol_range,
    parse_funding_response,
)


def test_funding_history_request_payload_is_flat_not_nested() -> None:
    # Deliberately different from candleSnapshot's {"type","req":{...}} shape
    # — a real, easy-to-get-wrong distinction, verified against the live API.
    payload = funding_history_request("BTC", 1000, 2000)
    assert payload == {
        "type": "fundingHistory",
        "coin": "BTC",
        "startTime": 1000,
        "endTime": 2000,
    }


def test_parse_funding_response_casts_string_fields() -> None:
    rows = [
        {"coin": "BTC", "fundingRate": "0.0000084964", "premium": "-0.0004320292", "time": 1000},
        {"coin": "BTC", "fundingRate": "0.0000110841", "premium": "-0.0004113275", "time": 4600000},
    ]
    frame = parse_funding_response(rows, "BTC")

    assert frame.height == 2
    assert frame["symbol"].to_list() == ["BTC", "BTC"]
    assert frame["source"].unique().to_list() == ["hyperliquid_info_api"]
    assert frame["funding_rate"].dtype == pl.Float64
    assert frame["funding_rate"].to_list() == pytest.approx([0.0000084964, 0.0000110841])
    assert frame["premium"].to_list() == pytest.approx([-0.0004320292, -0.0004113275])
    assert frame["open_time_ms"].is_sorted()


def test_parse_funding_response_empty_list_returns_empty_frame() -> None:
    frame = parse_funding_response([], "BTC")
    assert frame.height == 0
    assert set(frame.columns) == {"symbol", "open_time_ms", "funding_rate", "premium", "source"}


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_day_funding_uses_inclusive_end_boundary() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    with _mock_transport(handler) as client:
        fetch_day_funding("BTC", date(2026, 6, 26), client=client)

    payload = captured["payload"]
    day_start_ms = 1782432000000
    assert payload["startTime"] == day_start_ms
    assert payload["endTime"] == day_start_ms + 24 * 3600 * 1000 - 1
    assert payload["coin"] == "BTC"
    assert "req" not in payload  # flat shape, not nested


def test_fetch_day_funding_returns_parsed_json() -> None:
    body = [{"coin": "BTC", "fundingRate": "0.0001", "premium": "0.0002", "time": 1782432000000}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with _mock_transport(handler) as client:
        result = fetch_day_funding("BTC", date(2026, 6, 26), client=client)

    assert result == body


def test_fetch_day_funding_retries_then_raises_on_persistent_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scalpbot.data.hyperliquid_funding.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    with _mock_transport(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_day_funding("BTC", date(2026, 6, 26), client=client, max_retries=2)

    assert calls["n"] == 3


def test_fetch_day_funding_retries_on_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scalpbot.data.hyperliquid_funding.time.sleep", lambda _s: None)
    body = [{"coin": "BTC", "fundingRate": "0.0001", "premium": "0.0002", "time": 1782432000000}]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json=body)

    with _mock_transport(handler) as client:
        result = fetch_day_funding("BTC", date(2026, 6, 26), client=client, max_retries=3)

    assert result == body
    assert calls["n"] == 3


def test_ingest_symbol_range_writes_partitions_and_summarizes(tmp_path: Path) -> None:
    day_start_ms = 1782432000000
    full_day = [
        {
            "coin": "BTC",
            "fundingRate": "0.0001",
            "premium": "0.0002",
            "time": day_start_ms + h * 3600 * 1000,
        }
        for h in range(24)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=full_day)

    with _mock_transport(handler) as client:
        summary = ingest_symbol_range(
            "BTC",
            date(2026, 6, 26),
            date(2026, 6, 26),
            data_root=tmp_path,
            client=client,
        )

    assert summary.days_total == 1
    assert summary.days_fetched == 1
    assert summary.days_failed == 0

    written = tmp_path / "hyperliquid" / "funding" / "BTC" / OUTPUT_INTERVAL / "2026-06-26.parquet"
    assert written.exists()
    assert pl.read_parquet(written).height == 24


def test_ingest_symbol_range_skips_already_complete_partition(tmp_path: Path) -> None:
    from scalpbot.data.paths import partition_path

    final_path = partition_path(tmp_path, "hyperliquid", "funding", "BTC", "1h", date(2026, 6, 26))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"open_time_ms": list(range(24))}).write_parquet(final_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not fetch an already-complete partition")

    with _mock_transport(handler) as client:
        summary = ingest_symbol_range(
            "BTC",
            date(2026, 6, 26),
            date(2026, 6, 26),
            data_root=tmp_path,
            client=client,
        )

    assert summary.days_skipped_existing == 1
    assert summary.days_fetched == 0


def test_ingest_symbol_range_records_empty_response(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with _mock_transport(handler) as client:
        summary = ingest_symbol_range(
            "BTC",
            date(2026, 6, 26),
            date(2026, 6, 26),
            data_root=tmp_path,
            client=client,
        )

    assert summary.days_empty == 1
    assert summary.days_fetched == 0


def test_ingest_symbol_range_end_none_stops_at_yesterday(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import datetime

    fixed_now = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr("scalpbot.data.hyperliquid_funding.datetime", _FixedDatetime)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with _mock_transport(handler) as client:
        summary = ingest_symbol_range(
            "BTC",
            date(2026, 7, 25),
            None,
            data_root=tmp_path,
            client=client,
        )

    assert summary.days_total == 1  # only 2026-07-25, never today (07-26)
