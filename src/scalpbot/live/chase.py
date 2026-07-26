"""Bounded maker chase + rate-limit budgeter (PLAN.md Tasks 1.4, 3.1).

Chase: ALO at best bid/ask; if unfilled in `reprice_after_s`, cancel/replace at
the new best, max `max_retries`; abort entirely if price moved more than
`abort_after_ticks` from signal price (a runaway move turns a mean-reversion
entry into an unvalidated momentum entry).

Budgeter: token buckets for BOTH Hyperliquid limits — per-IP aggregate weight
(1200/min) and address-based (1 req per 1 USDC traded, 10k initial buffer).
Every outbound request in the process passes through this module; it refuses
requests rather than letting the venue reject them.
"""

from __future__ import annotations


class RateBudgeter:
    def __init__(self, ip_weight_per_min: int, address_buffer: int) -> None:
        raise NotImplementedError("Phase 1 Task 1.4")

    async def acquire(self, weight: int) -> None:
        """Blocks (or raises BudgetExhausted for non-critical paths) until budget allows."""
        raise NotImplementedError

    def on_volume_traded(self, usdc: float) -> None:
        """Address budget replenishes with traded volume."""
        raise NotImplementedError


class BudgetExhausted(Exception):
    pass
