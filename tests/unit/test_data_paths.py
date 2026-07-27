from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from scalpbot.data.paths import partition_is_complete, partition_path, tmp_path


def test_partition_path_layout() -> None:
    root = Path("data")
    path = partition_path(root, "binance", "klines", "BTCUSDT", "1s", date(2024, 7, 1))
    assert path == root / "binance" / "klines" / "BTCUSDT" / "1s" / "2024-07-01.parquet"


def test_tmp_path_appends_tmp_suffix() -> None:
    final = Path("data/binance/klines/BTCUSDT/1s/2024-07-01.parquet")
    assert tmp_path(final) == Path("data/binance/klines/BTCUSDT/1s/2024-07-01.parquet.tmp")


def _write_frame(path: Path, rows: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"open_time_ms": rows}).write_parquet(path)


def test_partition_is_complete_false_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "2024-07-01.parquet"
    assert partition_is_complete(missing, min_rows=1, max_rows=10) is False


def test_partition_is_complete_true_for_well_formed_sorted_file(tmp_path: Path) -> None:
    path = tmp_path / "2024-07-01.parquet"
    _write_frame(path, [1000, 2000, 3000, 4000, 5000])
    assert partition_is_complete(path, min_rows=3, max_rows=10) is True


def test_partition_is_complete_false_for_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "2024-07-01.parquet"
    path.write_bytes(b"not a real parquet file")
    assert partition_is_complete(path, min_rows=1, max_rows=10) is False


def test_partition_is_complete_false_for_unsorted_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "2024-07-01.parquet"
    _write_frame(path, [1000, 3000, 2000, 4000, 5000])
    assert partition_is_complete(path, min_rows=3, max_rows=10) is False


def test_partition_is_complete_false_for_duplicate_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "2024-07-01.parquet"
    _write_frame(path, [1000, 2000, 2000, 3000, 4000])
    assert partition_is_complete(path, min_rows=3, max_rows=10) is False


def test_partition_is_complete_false_when_row_count_below_min(tmp_path: Path) -> None:
    path = tmp_path / "2024-07-01.parquet"
    _write_frame(path, [1000, 2000])
    assert partition_is_complete(path, min_rows=5, max_rows=10) is False


def test_partition_is_complete_false_when_row_count_above_max(tmp_path: Path) -> None:
    path = tmp_path / "2024-07-01.parquet"
    _write_frame(path, [1000, 2000, 3000, 4000, 5000])
    assert partition_is_complete(path, min_rows=1, max_rows=3) is False
