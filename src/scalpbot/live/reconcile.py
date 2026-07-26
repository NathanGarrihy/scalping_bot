"""Boot-time reconciliation (PLAN.md Task 1.3): journal intent vs exchange truth.

Outcome must be one of: clean resume, safe repair (e.g. re-place a missing
stop), or HALT with alert. Kill criterion: any path that could duplicate an
order or leave a position without a stop is a design bug, not an edge case.
"""

from __future__ import annotations

from scalpbot.live.journal import Journal
from scalpbot.venues.base import AccountState


async def reconcile(journal: Journal, exchange_state: AccountState) -> str:
    """Returns the recovered engine disposition: 'resume' | 'repaired' | 'halt'."""
    raise NotImplementedError("Phase 1 Task 1.3")
