"""ExchangeAdapter — the venue-agnostic seam (PLAN.md §10).

Hyperliquid is the first implementation; a Kraken adapter is the regulatory
hedge. Anything the engine needs from a venue must be expressible through this
protocol; if it isn't, extend the protocol, never bypass it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from scalpbot.core.events import Event, Side


@dataclass(frozen=True, slots=True)
class OrderAck:
    cloid: str
    accepted: bool
    reason: str | None = None  # e.g. ALO order would have crossed → rejected


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    side: Side
    sz: float
    entry_px: float
    leverage: float
    isolated: bool


@dataclass(frozen=True, slots=True)
class OpenOrder:
    symbol: str
    cloid: str
    side: Side
    px: float
    sz: float
    is_stop: bool
    reduce_only: bool


@dataclass(frozen=True, slots=True)
class AccountState:
    equity: float
    withdrawable: float
    positions: tuple[Position, ...]
    open_orders: tuple[OpenOrder, ...]


class ExchangeAdapter(Protocol):
    """All methods must route through the rate-limit budgeter internally.
    All order methods take idempotent cloids supplied by the caller (journaled
    before the call — see scalpbot.live.journal)."""

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def place_maker(
        self, symbol: str, side: Side, px: float, sz: float, cloid: str
    ) -> OrderAck:
        """Post-only / add-liquidity-only. A crossing price must be rejected by
        the venue, never converted to a taker fill."""
        ...

    async def place_bracket(
        self,
        symbol: str,
        stop_px: float,
        take_profit_px: float | None,
        cloid: str,
    ) -> OrderAck:
        """Position-tied, reduce-only stop-market (+ optional TP), natively
        grouped on the venue. Must survive partial fills."""
        ...

    async def cancel(self, symbol: str, cloid: str) -> OrderAck: ...

    async def cancel_all(self, symbol: str | None = None) -> None: ...

    async def flatten(self, symbol: str | None = None) -> None:
        """Market-close positions. Only legal for killswitch/watchdog/breaker paths."""
        ...

    async def account_state(self) -> AccountState:
        """Exchange truth for boot-time reconciliation against the journal."""
        ...

    def stream_events(self) -> AsyncIterator[Event]:
        """Unified stream of market + order events translated to core.events
        types. Fill status must come from here — never from REST polling."""
        ...
