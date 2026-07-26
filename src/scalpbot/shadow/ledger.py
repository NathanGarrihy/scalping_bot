"""Paper ledger for shadow-live (PLAN.md Phase 4).

Same binary, same config hash as live — only the ledger differs. Fills are
granted by backtest.fills (trade-through only) against the live stream; fees,
hourly funding, and slippage haircuts from backtest.costs. Artifacts feed
gates/gate4_shadow.py: 200+ trades, expectancy inside the Phase 0 Monte Carlo
band, signal frequency and fill rates matching backtest assumptions.
"""

from __future__ import annotations

from pathlib import Path


class ShadowLedger:
    def __init__(self, out_dir: Path) -> None:
        raise NotImplementedError("Phase 4")
