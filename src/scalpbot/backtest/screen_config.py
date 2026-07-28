"""Stage 1 coarse-screen parameter grid (PLAN.md Task 0.3).

Scoped to just the `screen:` block of configs/research.yaml, following the
same scoped-section pattern as `data/config.py` — unrelated sections
(`universe`, `costs`, `walkforward`, ...) are ignored here and can evolve
independently without breaking this loader.

Expands the grid into concrete `core.strategy.StrategyConfig` instances so
`vector_screen.py` and the eventual Stage 2 event-driven engine consume the
exact same config shape — one strategy config type, never a screen-only
lookalike.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import product
from pathlib import Path

import yaml
from pydantic import BaseModel

from scalpbot.core.strategy import BollingerConfig, RsiConfig, StrategyConfig


class _BollingerGrid(BaseModel):
    period: list[int]
    sigma: list[float]


class _RsiGrid(BaseModel):
    period: list[int]
    thresholds: list[tuple[float, float]]  # [oversold, overbought] pairs


class _ExitSpec(BaseModel):
    mode: str
    take_profit_pct: float | None = None
    stop_pct: float | None = None
    target: str | None = None
    time_stop_s: int | None = None


class ScreenConfig(BaseModel):
    timeframe: str
    bollinger: _BollingerGrid
    rsi: _RsiGrid
    exits: list[_ExitSpec]


def load_screen_config(path: Path | str = "configs/research.yaml") -> ScreenConfig:
    """Read and validate only the top-level `screen:` mapping of `path`."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ScreenConfig.model_validate(raw["screen"])


_SIGNAL_DIRECTIONS = ("mean_revert", "momentum")


def iter_configs(screen: ScreenConfig) -> Iterator[StrategyConfig]:
    """Cartesian product of the grid, yielded as ready-to-run StrategyConfigs.

    Adds a `signal_direction` axis on top of the yaml-defined grid:
    `mean_revert` (bet the band-pierce reverts, PLAN.md's named anchor) and
    `momentum` (bet it continues — the Task 0.3 "zoom out" round's structural
    contrast family). `momentum` only pairs with `bracket` exits — a
    `mean_revert` exit's "target: middle_band" is incoherent for a
    continuation bet, so that combination is skipped, not generated and
    silently dropped later.

    Naming is deterministic (`screen_<params>`) so the research-ledger config
    hash (derived from the serialized config) is stable across repeated runs
    of the same grid.
    """
    for period, sigma, rsi_period, (oversold, overbought), exit_spec, direction in product(
        screen.bollinger.period,
        screen.bollinger.sigma,
        screen.rsi.period,
        screen.rsi.thresholds,
        screen.exits,
        _SIGNAL_DIRECTIONS,
    ):
        if direction == "momentum" and exit_spec.mode == "mean_revert":
            continue

        # `stop_pct` is the hard stop / R-risk-unit in every mode (PLAN.md Task
        # 3.2: every position keeps a resting stop regardless of how the
        # take-profit side works) — kept flat here rather than nested under
        # `bracket`/`mean_revert` since `vector_screen.py` reads it unconditionally.
        exits: dict = {"mode": exit_spec.mode, "stop_pct": exit_spec.stop_pct}
        if exit_spec.mode == "bracket":
            exits["take_profit_pct"] = exit_spec.take_profit_pct
        elif exit_spec.mode == "mean_revert":
            exits["target"] = exit_spec.target
            exits["time_stop_s"] = exit_spec.time_stop_s

        name = (
            f"screen_bb{period}_{sigma:g}sd_rsi{rsi_period}_"
            f"{oversold:g}-{overbought:g}_{exit_spec.mode}_{direction}"
        )
        yield StrategyConfig(
            name=name,
            status="CANDIDATE",
            timeframe=screen.timeframe,
            bollinger=BollingerConfig(period=period, sigma=sigma),
            rsi=RsiConfig(period=rsi_period, overbought=overbought, oversold=oversold),
            exits=exits,
            signal_direction=direction,
        )
