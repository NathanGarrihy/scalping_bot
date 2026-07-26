"""Sizing, correlation cap, and circuit breakers (PLAN.md Tasks 2.3, and §8 sizing).

Pure functions/state — the live engine and backtest both enforce risk through
this module, so a breaker that would have halted the backtest halts live too.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Mirror of configs/live.yaml `risk:`. Null-derived fields (consecutive_loss_halt,
    vol_halt_percentile) must be populated from Phase 0 gate artifacts before live."""

    leverage: float
    margin_per_trade_eur: float
    max_concurrent_positions: int
    daily_loss_halt_pct: float
    consecutive_loss_halt: int | None
    vol_halt_percentile: float | None


def position_size(equity_eur: float, limits: RiskLimits, px: float) -> float:
    """Fixed-margin sizing: margin_per_trade × leverage notional, never scaling
    with equity growth during burn-in. Must refuse full-equity margin (Phase 5
    kill criterion)."""
    raise NotImplementedError("blocked on Phase 0 gate")


class CircuitBreakers:
    """Three-layer halt discipline: daily loss, consecutive losses, volatility
    regime. Thresholds are empirical (Monte Carlo artifacts), never round numbers."""

    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits
        raise NotImplementedError("blocked on Phase 0 gate")

    def on_trade_closed(self, pnl_eur: float, utc_day: int) -> str | None:
        """Returns a halt reason or None."""
        raise NotImplementedError

    def on_realized_vol(self, vol_percentile: float) -> str | None:
        raise NotImplementedError


def correlation_cap_ok(open_positions: int, limits: RiskLimits) -> bool:
    """Max 1–2 concurrent positions across the basket — five correlated longs
    are one 5x-sized trade."""
    return open_positions < limits.max_concurrent_positions
