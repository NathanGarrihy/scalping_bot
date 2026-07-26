"""Venue-agnostic event types consumed by the strategy core.

Contract (PLAN.md §10): events are immutable, carry exchange timestamps in ms,
and are the *only* input vocabulary of the core. Every driver — backtest replay,
shadow, live websocket — must translate its source into exactly these types.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    open_time_ms: int
    interval: str  # e.g. "1s"
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class BookTop:
    symbol: str
    ts_ms: int
    bid_px: float
    bid_sz: float
    ask_px: float
    ask_sz: float

    @property
    def spread_bps(self) -> float:
        mid = (self.bid_px + self.ask_px) / 2
        return (self.ask_px - self.bid_px) / mid * 10_000


@dataclass(frozen=True, slots=True)
class Fill:
    symbol: str
    ts_ms: int
    cloid: str
    side: Side
    px: float
    sz: float
    is_maker: bool
    fee: float  # negative = rebate received


@dataclass(frozen=True, slots=True)
class OrderUpdate:
    symbol: str
    ts_ms: int
    cloid: str
    status: OrderStatus
    filled_sz: float
    remaining_sz: float


@dataclass(frozen=True, slots=True)
class FundingEvent:
    symbol: str
    ts_ms: int
    rate_hourly: float  # Hyperliquid funding accrues hourly
    payment: float      # signed; negative = paid by us


@dataclass(frozen=True, slots=True)
class Timer:
    """Periodic tick injected by the driver — the core never reads a clock."""

    ts_ms: int


Event = Candle | BookTop | Fill | OrderUpdate | FundingEvent | Timer
