"""Durable state journal (PLAN.md Task 1.3): SQLite in WAL mode.

Contract: every order intent and state transition is journaled BEFORE the API
call fires, keyed by idempotent cloid, so a crash mid-request can never
double-fire. The exchange is the source of truth; the journal records intent —
together they distinguish "never sent" from "sent, response lost", which
polling alone cannot. Chaos test: kill -9 mid-trade, restart, recover.
"""

from __future__ import annotations

from pathlib import Path


class Journal:
    def __init__(self, db_path: Path) -> None:
        raise NotImplementedError("Phase 1 Task 1.3")

    def record_intent(self, cloid: str, action_json: str, ts_ms: int) -> None:
        """Durable (fsync'd WAL) before returning."""
        raise NotImplementedError

    def record_outcome(self, cloid: str, outcome_json: str, ts_ms: int) -> None:
        raise NotImplementedError

    def pending_intents(self) -> list[tuple[str, str]]:
        """Intents with no recorded outcome — the reconciliation worklist."""
        raise NotImplementedError

    def next_cloid(self) -> str:
        """Monotonic, collision-free, journaled at allocation time."""
        raise NotImplementedError
