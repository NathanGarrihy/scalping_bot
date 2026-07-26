"""Vectorized (polars) coarse grid screen — Stage 1 of Task 0.3.

Prunes dead parameter regions cheaply before the event-driven engine runs.
Screening only: results are never cited as gate evidence. Every configuration
screened still gets a research-ledger row (multiple-testing honesty).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl


def screen_grid(corpus: pl.LazyFrame, grid: dict, ledger_path: Path) -> pl.DataFrame:
    """Returns surviving configs; appends every evaluated config to the ledger."""
    raise NotImplementedError("Phase 0 Task 0.3")
