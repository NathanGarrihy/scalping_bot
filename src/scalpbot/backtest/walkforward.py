"""Walk-forward protocol with purged/embargoed splits (PLAN.md Task 0.3).

Anti-overfitting hard requirements enforced here:
- train/test windows roll forward; an embargo gap prevents leakage through
  overlapping holding periods
- the single-use holdout (most recent N months) is excluded from every split
  and evaluated exactly once, after iteration stops
- parameter-plateau check: the winner's neighbors must also be profitable
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Split:
    train_start: date
    train_end: date
    embargo_end: date
    test_start: date
    test_end: date


def make_splits(
    start: date, end: date, train_months: int, test_months: int, embargo_days: int
) -> list[Split]:
    raise NotImplementedError("Phase 0 Task 0.3")


def plateau_check(grid_results: dict, winner_key: tuple, min_neighbor_expectancy: float) -> bool:
    """Reject spike optima: every neighboring config must clear the bar too."""
    raise NotImplementedError("Phase 0 Task 0.3")


def deflated_expectancy(raw_expectancy: float, n_trials: int, n_trades: int) -> float:
    """Multiple-testing discount driven by the research-ledger trial count."""
    raise NotImplementedError("Phase 0 Task 0.3")
