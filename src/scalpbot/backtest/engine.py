"""Event-driven backtest: replays historical events through core.strategy.decide,
applying fills.py and costs.py to the emitted actions.

This is the authoritative backtest — same strategy code as shadow and live.
Output artifact: a trade list (parquet) + summary JSON consumed by gates/.
"""

from __future__ import annotations

from pathlib import Path

from scalpbot.core.strategy import StrategyConfig


def run_backtest(
    events_path: Path,
    config: StrategyConfig,
    cost_params_path: Path,
    out_dir: Path,
) -> Path:
    """Returns the path of the summary artifact for gate consumption."""
    raise NotImplementedError("Phase 0 Task 0.3")
