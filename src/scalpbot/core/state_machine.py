"""Per-symbol execution state machine (PLAN.md Task 2.2).

Explicit transition table; illegal transitions raise. Property tests in
tests/property/ assert the invariants (no concurrent opposite signals, no
position without a resting stop while MANAGING_POSITION).
"""

from __future__ import annotations

from enum import StrEnum


class BotState(StrEnum):
    WAITING = "waiting"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_PLACED = "order_placed"
    FILLED = "filled"
    MANAGING_POSITION = "managing_position"
    FLAT = "flat"
    HALTED = "halted"


TRANSITIONS: dict[BotState, frozenset[BotState]] = {
    BotState.WAITING: frozenset({BotState.SIGNAL_GENERATED, BotState.HALTED}),
    # back to WAITING when filters reject the signal or the chase aborts
    BotState.SIGNAL_GENERATED: frozenset(
        {BotState.ORDER_PLACED, BotState.WAITING, BotState.HALTED}
    ),
    # back to WAITING when the maker order is canceled unfilled (chase exhausted)
    BotState.ORDER_PLACED: frozenset({BotState.FILLED, BotState.WAITING, BotState.HALTED}),
    BotState.FILLED: frozenset({BotState.MANAGING_POSITION, BotState.HALTED}),
    BotState.MANAGING_POSITION: frozenset({BotState.FLAT, BotState.HALTED}),
    BotState.FLAT: frozenset({BotState.WAITING}),
    # HALTED exits only via explicit operator resume
    BotState.HALTED: frozenset({BotState.WAITING}),
}


class IllegalTransition(Exception):
    def __init__(self, src: BotState, dst: BotState) -> None:
        super().__init__(f"illegal transition {src} -> {dst}")
        self.src = src
        self.dst = dst


def can_transition(src: BotState, dst: BotState) -> bool:
    return dst in TRANSITIONS[src]


def transition(src: BotState, dst: BotState) -> BotState:
    """Validate and return the new state. Journaling is the caller's job
    (journal-before-send happens in scalpbot.live.journal)."""
    if not can_transition(src, dst):
        raise IllegalTransition(src, dst)
    return dst
