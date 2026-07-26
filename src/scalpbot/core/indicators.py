"""O(1) rolling indicators (PLAN.md Task 2.1).

Must produce bit-identical values in backtest replay and live streaming —
these run inside the deterministic core, so no numpy state or floating-point
reductions that depend on batch shape. Welford-style running moments for the
Bollinger band; Wilder smoothing for RSI.
"""

from __future__ import annotations


class RollingBollinger:
    """3σ Bollinger band over a fixed-period rolling window, O(1) per update."""

    def __init__(self, period: int, sigma: float) -> None:
        self.period = period
        self.sigma = sigma
        raise NotImplementedError("blocked on Phase 0 gate")

    def update(self, close: float) -> tuple[float, float, float] | None:
        """Feed one close; returns (lower, middle, upper) once warm, else None."""
        raise NotImplementedError

    @property
    def is_warm(self) -> bool:
        raise NotImplementedError


class RollingRsi:
    """Fast RSI (Wilder smoothing), O(1) per update."""

    def __init__(self, period: int) -> None:
        self.period = period
        raise NotImplementedError("blocked on Phase 0 gate")

    def update(self, close: float) -> float | None:
        """Feed one close; returns RSI in [0, 100] once warm, else None."""
        raise NotImplementedError
