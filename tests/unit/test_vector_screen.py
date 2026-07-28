from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from scalpbot.backtest.costs import CostParams
from scalpbot.backtest.vector_screen import _evaluate_config, screen_grid
from scalpbot.core.strategy import BollingerConfig, RsiConfig, StrategyConfig

_COST_PARAMS = CostParams(maker_fee_bps=1.5, taker_fee_bps=4.5, stop_slippage_haircut_bps=50.0)
_MAKER_FRAC = 1.5 / 10_000
_TAKER_FRAC = (4.5 + 50.0) / 10_000


def _bracket_config(*, oversold: float = 99.0, overbought: float = 101.0) -> StrategyConfig:
    """period=5/sigma=1.0 keeps the rolling window small enough to hand-verify
    by index; oversold=99/overbought=101 make the RSI leg of the entry
    condition unconditionally true/false so only the Bollinger-band piercing
    controls whether a signal fires — avoids needing to hand-compute Wilder
    RSI to reason about these tests.
    """
    return StrategyConfig(
        name="hand_verify_bracket",
        status="CANDIDATE",
        timeframe="1s",
        bollinger=BollingerConfig(period=5, sigma=1.0),
        rsi=RsiConfig(period=2, overbought=overbought, oversold=oversold),
        exits={"mode": "bracket", "stop_pct": 6.0, "take_profit_pct": 2.0},
    )


def _drop_and_hold_corpus(hold_close: float, n_tail: int = 30) -> pl.DataFrame:
    """10-bar alternating warmup (100/101), a single drop to close=90.0 at
    index 10 (verified below to pierce the period=5/sigma=1.0 lower band),
    then `n_tail` flat bars at `hold_close`.

    Lower band at index 10: window = closes[6..10] = [100, 101, 100, 101, 90]
    -> mean=98.4, population std=sqrt(17.84)=4.224..., lower_band =
    98.4 - 1.0*4.224 = 94.18 > 90 -> close(90) < lower_band, signal fires.
    """
    warmup = [100.0, 101.0] * 5
    closes = warmup + [90.0] + [hold_close] * n_tail
    return pl.DataFrame(
        {
            "open_time_ms": [i * 1000 for i in range(len(closes))],
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1.0] * len(closes),
        }
    )


def _momentum_config(*, oversold: float = 101.0, overbought: float = -1.0) -> StrategyConfig:
    """momentum's long entry is `close > upper_band & rsi >= overbought`;
    overbought=-1 makes the RSI leg unconditionally true (real RSI is always
    >= 0), isolating the Bollinger-band piercing the same way `_bracket_config`
    isolates it for mean_revert. oversold=101 keeps the mirrored short leg
    unreachable (real RSI never exceeds 100), so these tests stay long-only.
    """
    return StrategyConfig(
        name="hand_verify_momentum",
        status="CANDIDATE",
        timeframe="1s",
        bollinger=BollingerConfig(period=5, sigma=1.0),
        rsi=RsiConfig(period=2, overbought=overbought, oversold=oversold),
        exits={"mode": "bracket", "stop_pct": 6.0, "take_profit_pct": 2.0},
        signal_direction="momentum",
    )


def _spike_up_and_hold_corpus(hold_close: float, n_tail: int = 30) -> pl.DataFrame:
    """Mirror of `_drop_and_hold_corpus`: same 10-bar alternating warmup, but a
    spike *up* to close=110.0 at index 10 (pierces the upper band), then
    `n_tail` flat bars at `hold_close`.

    Upper band at index 10: window = closes[6..10] = [100, 101, 100, 101, 110]
    -> mean=102.4, population std=sqrt(14.64)=3.826..., upper_band =
    102.4 + 1.0*3.826 = 106.23 < 110 -> close(110) > upper_band, signal fires.
    """
    warmup = [100.0, 101.0] * 5
    closes = warmup + [110.0] + [hold_close] * n_tail
    return pl.DataFrame(
        {
            "open_time_ms": [i * 1000 for i in range(len(closes))],
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1.0] * len(closes),
        }
    )


def test_screen_grid_momentum_take_profit_hit_hand_verified_r(tmp_path: Path) -> None:
    # Tail flat at 115.0: high=115.0 >= tp_price(110*1.02=112.2) on the first
    # forward bar; low=115.0 never reaches sl_price(110*0.94=103.4). Same
    # expected-R formula as the mean_revert TP test — same config economics,
    # only the entry direction differs.
    corpus = _spike_up_and_hold_corpus(hold_close=115.0)
    config = _momentum_config()

    result = screen_grid(corpus, "TEST", [config], _COST_PARAMS, tmp_path / "ledger.md")

    assert result["n_trades"][0] == 1
    tp_pct, stop_pct = 0.02, 0.06
    expected_r = tp_pct / stop_pct - (_MAKER_FRAC + _MAKER_FRAC) / stop_pct
    assert result["expectancy_r"][0] == pytest.approx(expected_r, abs=1e-9)
    assert result["win_rate"][0] == pytest.approx(1.0)


def test_screen_grid_momentum_stop_loss_hit_hand_verified_r(tmp_path: Path) -> None:
    # Tail flat at 100.0: low=100.0 <= sl_price(103.4); high=100.0 never
    # reaches tp_price(112.2) -> unambiguous stop-loss exit.
    corpus = _spike_up_and_hold_corpus(hold_close=100.0)
    config = _momentum_config()

    result = screen_grid(corpus, "TEST", [config], _COST_PARAMS, tmp_path / "ledger.md")

    assert result["n_trades"][0] == 1
    stop_pct = 0.06
    expected_r = -1.0 - (_MAKER_FRAC + _TAKER_FRAC) / stop_pct
    assert result["expectancy_r"][0] == pytest.approx(expected_r, abs=1e-9)
    assert result["win_rate"][0] == pytest.approx(0.0)


def test_screen_grid_take_profit_hit_hand_verified_r(tmp_path: Path) -> None:
    # Tail flat at 92.0: high=92.0 >= tp_price(90*1.02=91.8) on the very
    # first forward bar; low=92.0 never reaches sl_price(90*0.94=84.6).
    corpus = _drop_and_hold_corpus(hold_close=92.0)
    config = _bracket_config()

    result = screen_grid(corpus, "TEST", [config], _COST_PARAMS, tmp_path / "ledger.md")

    assert result["n_trades"][0] == 1
    tp_pct, stop_pct = 0.02, 0.06
    expected_r = tp_pct / stop_pct - (_MAKER_FRAC + _MAKER_FRAC) / stop_pct
    assert result["expectancy_r"][0] == pytest.approx(expected_r, abs=1e-9)
    assert result["win_rate"][0] == pytest.approx(1.0)


def test_screen_grid_stop_loss_hit_hand_verified_r(tmp_path: Path) -> None:
    # Tail flat at 80.0: low=80.0 <= sl_price(84.6); high=80.0 never reaches
    # tp_price(91.8) -> unambiguous stop-loss exit, no tie-break involved.
    corpus = _drop_and_hold_corpus(hold_close=80.0)
    config = _bracket_config()

    result = screen_grid(corpus, "TEST", [config], _COST_PARAMS, tmp_path / "ledger.md")

    assert result["n_trades"][0] == 1
    stop_pct = 0.06
    expected_r = -1.0 - (_MAKER_FRAC + _TAKER_FRAC) / stop_pct
    assert result["expectancy_r"][0] == pytest.approx(expected_r, abs=1e-9)
    assert result["win_rate"][0] == pytest.approx(0.0)


def test_screen_grid_no_signal_produces_zero_trades_but_still_logs(tmp_path: Path) -> None:
    corpus = _drop_and_hold_corpus(hold_close=92.0)
    # oversold=-1 and overbought=101 are both unreachable by a real RSI (0-100),
    # so neither long nor short entries can ever fire.
    config = _bracket_config(oversold=-1.0, overbought=101.0)
    ledger_path = tmp_path / "ledger.md"

    result = screen_grid(corpus, "TEST", [config], _COST_PARAMS, ledger_path)

    assert result["n_trades"][0] == 0
    assert result["expectancy_r"][0] == 0.0
    assert result["win_rate"][0] == 0.0
    assert "0.0000R, 0" in ledger_path.read_text(encoding="utf-8")


def test_screen_grid_appends_exactly_one_ledger_row_per_config(tmp_path: Path) -> None:
    corpus = _drop_and_hold_corpus(hold_close=92.0)
    configs = [_bracket_config(), _bracket_config(oversold=-1.0, overbought=101.0)]
    ledger_path = tmp_path / "ledger.md"

    result = screen_grid(corpus, "TEST", configs, _COST_PARAMS, ledger_path)

    assert result.height == 2
    data_rows = [
        line
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and "Date (UTC)" not in line and ":---" not in line
    ]
    assert len(data_rows) == 2


def test_evaluate_config_suppresses_overlapping_entries() -> None:
    """Two consecutive bars both satisfy the long-entry condition (indices 0
    and 1); only index 0's trade should be accepted — index 1 falls inside
    index 0's max-hold window (`4 * bollinger.period` = 20 bars for this
    config), which the position-sequencing simplification treats as "still
    open" (see vector_screen module docstring).
    """
    n = 40
    lower_band = [95.0, 95.0] + [50.0] * (n - 2)  # only rows 0,1 have close(90) < lower_band
    indicators = pl.DataFrame(
        {
            "open_time_ms": [i * 1000 for i in range(n)],
            "close": [90.0] * n,
            "high": [90.0] * n,
            "low": [90.0] * n,
            "signal_value": [90.0] * n,  # entry detection reads this, not close directly
            "middle_band": [100.0] * n,
            "upper_band": [110.0] * n,
            "lower_band": lower_band,
            "rsi": [10.0] * n,
        }
    )
    config = _bracket_config()

    trades = _evaluate_config(indicators, config, _COST_PARAMS)

    assert trades.height == 1
    assert trades["direction"][0] == 1
