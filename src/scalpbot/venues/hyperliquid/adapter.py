"""HyperliquidAdapter: ExchangeAdapter implementation (PLAN.md Phase 1/3).

Blocked on Phase 0 gate — signatures only. Implementation notes for later:
- wrap hyperliquid-python-sdk Exchange/Info clients; ws subscriptions for
  candles, bbo (fast where needed), userEvents, orderUpdates
- every request passes through live.chase's rate budgeter
- cloid = idempotent client order id from the journal
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from scalpbot.core.events import Event, Side
from scalpbot.venues.base import AccountState, OrderAck


class HyperliquidAdapter:
    def __init__(
        self,
        *,
        account_address: str,
        agent_private_key: str,
        subaccount: str | None,
        testnet: bool,
    ) -> None:
        self.testnet = testnet
        raise NotImplementedError("blocked on Phase 0 gate (gates/gate0_edge.py)")

    async def connect(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def place_maker(
        self, symbol: str, side: Side, px: float, sz: float, cloid: str
    ) -> OrderAck:
        raise NotImplementedError

    async def place_bracket(
        self, symbol: str, stop_px: float, take_profit_px: float | None, cloid: str
    ) -> OrderAck:
        raise NotImplementedError

    async def cancel(self, symbol: str, cloid: str) -> OrderAck:
        raise NotImplementedError

    async def cancel_all(self, symbol: str | None = None) -> None:
        raise NotImplementedError

    async def flatten(self, symbol: str | None = None) -> None:
        raise NotImplementedError

    async def account_state(self) -> AccountState:
        raise NotImplementedError

    def stream_events(self) -> AsyncIterator[Event]:
        raise NotImplementedError
