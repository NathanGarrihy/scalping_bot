"""Phase 0 edge gate (PLAN.md §9).

PASS requires ALL of, computed from backtest artifacts:
- data integrity reports pass; regime coverage incl. ≥40% drawdown
- expectancy > 0.05R after hostile costs on walk-forward OOS
- single-use holdout positive (and marked consumed in the research ledger)
- edge present in ≥2 regimes
- parameter plateau check passed
- deflated (multiple-testing discounted) expectancy still clears the bar
"""

from __future__ import annotations

from _common import run


def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    run("gate0_edge", main)
