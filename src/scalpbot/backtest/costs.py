"""Cost model (PLAN.md Task 0.3): fees, hourly funding, stop-slippage haircut.

Parameters come from configs/research.yaml `costs:` and were verified against
Hyperliquid's own fee schedule (hyperliquid.gitbook.io/hyperliquid-docs/trading/fees,
checked 2026-07-27): base-tier (<$5M 14d volume) maker is a +1.5bps fee, not a
rebate — the rebate tier (>$500M 14d volume) is unreachable at this account's
size. Maker fee is charged on every maker entry fill; fills.py decides whether
a fill is granted at all, not whether it's charged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class CostParams:
    maker_fee_bps: float  # positive = fee paid; negative = rebate credited
    taker_fee_bps: float
    stop_slippage_haircut_bps: float


class _CostsSection(BaseModel):
    maker_fee_bps: float
    taker_fee_bps: float
    funding_cadence: str
    stop_slippage_haircut_bps_range: tuple[float, float]


def load_cost_params(path: Path | str = "configs/research.yaml") -> CostParams:
    """Read and validate only the top-level `costs:` mapping of `path`.

    Applies the *upper* (more pessimistic) bound of
    `stop_slippage_haircut_bps_range` as the fixed haircut, per PLAN.md Task
    0.3's hostile-fill-model requirement — the backtest should never assume
    the friendlier end of the range.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["costs"]
    section = _CostsSection.model_validate(raw)
    return CostParams(
        maker_fee_bps=section.maker_fee_bps,
        taker_fee_bps=section.taker_fee_bps,
        stop_slippage_haircut_bps=section.stop_slippage_haircut_bps_range[1],
    )


def entry_cost(notional: float, params: CostParams) -> float:
    """Fee charged (positive) or rebate credited (negative) on a maker entry fill."""
    return notional * params.maker_fee_bps / 10_000


def stop_exit_cost(notional: float, params: CostParams) -> float:
    """Taker fee + slippage haircut — cascades slip far worse than mid-book
    quotes suggest on high-beta alts."""
    return notional * (params.taker_fee_bps + params.stop_slippage_haircut_bps) / 10_000


def funding_accrual(notional: float, hourly_rates: list[float]) -> float:
    """Hyperliquid funding accrues hourly over the holding period.

    `hourly_rates` must already be signed relative to the position direction
    (positive = cost to the position, negative = payment to the position) —
    this function has no notion of side.
    """
    return notional * sum(hourly_rates)
