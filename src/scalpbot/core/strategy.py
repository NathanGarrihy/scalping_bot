"""The strategy brain: pure function (state, event, config) -> [actions].

This module is the single implementation of trading logic in the system.
Backtest (Phase 0), shadow (Phase 4), and live (Phase 5) all call `decide`.
Implementation is gated behind Phase 0 signal selection — signatures only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from scalpbot.core.events import Event, Side
from scalpbot.core.state_machine import BotState


class BollingerConfig(BaseModel):
    period: int
    sigma: float


class RsiConfig(BaseModel):
    period: int
    overbought: float
    oversold: float


class StrategyConfig(BaseModel):
    """Mirror of configs/strategy/*.yaml. status must be VALIDATED (hash-pinned)
    before this config may drive shadow or live trading."""

    name: str
    status: str  # CANDIDATE | VALIDATED
    timeframe: str
    bollinger: BollingerConfig
    rsi: RsiConfig
    exits: dict


# --- Actions: the core's entire output vocabulary -------------------------------

@dataclass(frozen=True, slots=True)
class PlaceMakerOrder:
    """ALO/post-only entry at best bid/ask. Never a taker order."""

    symbol: str
    side: Side
    px: float
    sz: float
    cloid: str


@dataclass(frozen=True, slots=True)
class PlaceBracket:
    """Native TP/SL grouping on the venue, reduce-only, position-tied."""

    symbol: str
    stop_px: float
    take_profit_px: float | None  # None when exit mode is mean-revert (managed exit)
    cloid: str


@dataclass(frozen=True, slots=True)
class CancelOrder:
    symbol: str
    cloid: str


@dataclass(frozen=True, slots=True)
class Flatten:
    symbol: str
    reason: str


@dataclass(frozen=True, slots=True)
class Halt:
    reason: str


Action = PlaceMakerOrder | PlaceBracket | CancelOrder | Flatten | Halt


@dataclass(frozen=True, slots=True)
class SymbolState:
    """Complete per-symbol strategy state. Immutable: `decide` returns a new one."""

    state: BotState = BotState.WAITING
    signal_px: float | None = None
    signal_side: Side | None = None
    chase_count: int = 0
    entry_px: float | None = None
    position_sz: float = 0.0
    extra: dict = field(default_factory=dict)


def decide(
    state: SymbolState, event: Event, config: StrategyConfig
) -> tuple[SymbolState, list[Action]]:
    """Pure decision function. No I/O, no clock, no randomness — timestamps come
    from the event, order sizing comes from core.risk, ids from the driver-supplied
    cloid sequence carried in state.extra.

    Implemented after Phase 0 selects the validated signal configuration.
    """
    raise NotImplementedError("blocked on Phase 0 gate (gates/gate0_edge.py)")
