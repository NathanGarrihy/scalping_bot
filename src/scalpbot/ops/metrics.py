"""Structured JSONL logs + SQLite metrics (PLAN.md §10).

Every fill also lands in a tax export table (timestamps, fees) for Irish
CGT/income reporting (§11).
"""

from __future__ import annotations

from pathlib import Path


class MetricsSink:
    def __init__(self, jsonl_path: Path, db_path: Path) -> None:
        raise NotImplementedError("Phase 1")

    def emit(self, kind: str, payload: dict, ts_ms: int) -> None:
        raise NotImplementedError
