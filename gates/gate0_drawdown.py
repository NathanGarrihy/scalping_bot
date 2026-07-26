"""Phase 0 drawdown gate: Monte Carlo P95 max drawdown ≤ 40% of equity at the
intended risk-per-trade. On PASS, writes the empirical thresholds
(consecutive-loss halt, drawdown kill level) that fill the nulls in
configs/live.yaml."""

from __future__ import annotations

from _common import run


def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    run("gate0_drawdown", main)
