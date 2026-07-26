"""Phase 5 burn-in gate: 100+ live trades inside empirical bands; realized
stop slippage ≤ 2x modeled haircut; realized maker-fill rate ≥ hostile model
grant rate; zero taker entries; zero full-equity sizing attempts."""

from __future__ import annotations

from _common import run


def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    run("gate5_live", main)
