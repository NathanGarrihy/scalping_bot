"""Hostile fill model (PLAN.md Task 0.3): trade-through only.

A resting maker order fills iff price trades *through* the limit level — touch
does not fill. Where HL L2 snapshots are available, queue position further
gates the fill. The same model runs in the Phase 4 shadow ledger; the Phase 5
gate compares its grant rate against realized maker fills.
"""

from __future__ import annotations

from scalpbot.core.events import Side


def maker_fill_granted(
    side: Side,
    limit_px: float,
    bar_high: float,
    bar_low: float,
) -> bool:
    """Strict trade-through: BUY fills only if bar_low < limit_px (not <=),
    SELL only if bar_high > limit_px."""
    raise NotImplementedError("Phase 0 Task 0.3")
