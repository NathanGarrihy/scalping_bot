"""Monte Carlo drawdown mapping (PLAN.md Task 0.4).

Resamples the validated trade sequence 10k times → empirical distributions of
max drawdown, P95 drawdown, longest losing streak. These artifacts set the
live kill thresholds and circuit-breaker levels (configs/live.yaml nulls).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DrawdownBands:
    expected_max_dd_pct: float
    p95_max_dd_pct: float
    longest_losing_streak: int
    p95_losing_streak: int


def resample_drawdowns(trades_path: Path, resamples: int, seed: int) -> DrawdownBands:
    """Seeded for reproducibility — gate artifacts must be re-derivable."""
    raise NotImplementedError("Phase 0 Task 0.4")
