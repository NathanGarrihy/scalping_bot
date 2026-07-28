from __future__ import annotations

from pathlib import Path

import pytest

from scalpbot.backtest.costs import (
    CostParams,
    entry_cost,
    funding_accrual,
    load_cost_params,
    stop_exit_cost,
)

VALID_YAML = """
costs:
  maker_fee_bps: 1.5
  taker_fee_bps: 4.5
  funding_cadence: hourly
  stop_slippage_haircut_bps_range: [30, 50]
"""


def test_entry_cost_positive_fee_is_a_cost() -> None:
    params = CostParams(maker_fee_bps=1.5, taker_fee_bps=4.5, stop_slippage_haircut_bps=50.0)
    # 1.5bps on $10,000 notional = $1.50
    assert entry_cost(10_000.0, params) == pytest.approx(1.5)


def test_entry_cost_negative_fee_is_credited_as_a_rebate() -> None:
    params = CostParams(maker_fee_bps=-0.5, taker_fee_bps=4.5, stop_slippage_haircut_bps=50.0)
    # -0.5bps on $10,000 notional = -$0.50 (a credit, not a cost)
    assert entry_cost(10_000.0, params) == pytest.approx(-0.5)


def test_stop_exit_cost_combines_taker_fee_and_slippage_haircut() -> None:
    params = CostParams(maker_fee_bps=1.5, taker_fee_bps=4.5, stop_slippage_haircut_bps=50.0)
    # (4.5 + 50) bps on $10,000 = $54.50
    assert stop_exit_cost(10_000.0, params) == pytest.approx(54.5)


def test_funding_accrual_sums_pre_signed_hourly_rates() -> None:
    # $10,000 held 3 hours at rates already signed relative to the position:
    # 0.001 + (-0.0005) + 0.0002 = 0.0007
    result = funding_accrual(10_000.0, [0.001, -0.0005, 0.0002])
    assert result == pytest.approx(10_000.0 * 0.0007)


def test_funding_accrual_empty_rates_is_zero() -> None:
    assert funding_accrual(10_000.0, []) == 0.0


def test_load_cost_params_parses_real_research_yaml() -> None:
    params = load_cost_params("configs/research.yaml")
    # Verified against Hyperliquid's own fee docs 2026-07-27 — base tier
    # (<$5M 14d volume) maker is a +1.5bps cost, not a rebate.
    assert params.maker_fee_bps == pytest.approx(1.5)
    assert params.taker_fee_bps == pytest.approx(4.5)


def test_load_cost_params_applies_pessimistic_upper_haircut_bound(tmp_path: Path) -> None:
    config_path = tmp_path / "research.yaml"
    config_path.write_text(VALID_YAML, encoding="utf-8")

    params = load_cost_params(config_path)

    # range is [30, 50] — the hostile/pessimistic bound is the upper one
    assert params.stop_slippage_haircut_bps == pytest.approx(50.0)


def test_load_cost_params_ignores_other_top_level_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "research.yaml"
    config_path.write_text(
        VALID_YAML + "\nuniverse:\n  volume_rank_max: 40\n",
        encoding="utf-8",
    )

    params = load_cost_params(config_path)

    assert params.maker_fee_bps == pytest.approx(1.5)
