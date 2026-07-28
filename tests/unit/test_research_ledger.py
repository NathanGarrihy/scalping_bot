from __future__ import annotations

from pathlib import Path

from scalpbot.backtest.research_ledger import append_row, config_hash
from scalpbot.core.strategy import BollingerConfig, RsiConfig, StrategyConfig


def _config(**exits_overrides: object) -> StrategyConfig:
    exits: dict = {"mode": "bracket", "stop_pct": 6.0, "take_profit_pct": 2.0}
    exits.update(exits_overrides)
    return StrategyConfig(
        name="test_cfg",
        status="CANDIDATE",
        timeframe="1s",
        bollinger=BollingerConfig(period=1200, sigma=3.0),
        rsi=RsiConfig(period=5, overbought=85, oversold=15),
        exits=exits,
    )


def test_config_hash_stable_across_renamed_config() -> None:
    cfg_a = _config()
    cfg_b = StrategyConfig(
        name="renamed_but_same_params",
        status="CANDIDATE",
        timeframe=cfg_a.timeframe,
        bollinger=cfg_a.bollinger,
        rsi=cfg_a.rsi,
        exits=cfg_a.exits,
    )
    assert config_hash(cfg_a) == config_hash(cfg_b)


def test_config_hash_differs_for_different_params() -> None:
    cfg_a = _config()
    cfg_b = _config(take_profit_pct=3.0)
    assert config_hash(cfg_a) != config_hash(cfg_b)


def test_append_row_creates_ledger_with_header_when_missing(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.md"
    cfg = _config()

    append_row(
        config=cfg,
        symbol="BTCUSDT",
        data_range="2024-07-01..2026-04-01",
        splits="screen",
        expectancy_r=0.123,
        n_trades=42,
        ledger_path=ledger_path,
    )

    content = ledger_path.read_text(encoding="utf-8")
    assert "# Research Ledger" in content
    assert "| Date (UTC) | Config hash |" in content
    assert config_hash(cfg) in content
    assert "0.1230R, 42" in content
    assert "symbol=BTCUSDT" in content


def test_append_row_appends_without_duplicating_header(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.md"
    cfg = _config()

    append_row(
        config=cfg,
        symbol="BTCUSDT",
        data_range="r1",
        splits="s1",
        expectancy_r=0.1,
        n_trades=1,
        ledger_path=ledger_path,
    )
    append_row(
        config=cfg,
        symbol="ETHUSDT",
        data_range="r1",
        splits="s1",
        expectancy_r=0.2,
        n_trades=2,
        ledger_path=ledger_path,
    )

    content = ledger_path.read_text(encoding="utf-8")
    assert content.count("# Research Ledger") == 1
    assert content.count(config_hash(cfg)) == 2


def test_append_row_preserves_existing_content_instead_of_overwriting(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.md"
    ledger_path.write_text("# Research Ledger\n\n| existing | row |\n", encoding="utf-8")
    cfg = _config()

    append_row(
        config=cfg,
        symbol="BTCUSDT",
        data_range="r1",
        splits="s1",
        expectancy_r=0.1,
        n_trades=1,
        ledger_path=ledger_path,
    )

    content = ledger_path.read_text(encoding="utf-8")
    assert "| existing | row |" in content
    assert content.count("# Research Ledger") == 1


def test_append_row_includes_notes_alongside_symbol(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.md"
    cfg = _config()

    append_row(
        config=cfg,
        symbol="BTCUSDT",
        data_range="r1",
        splits="s1",
        expectancy_r=0.1,
        n_trades=1,
        notes="min_expectancy filter applied",
        ledger_path=ledger_path,
    )

    content = ledger_path.read_text(encoding="utf-8")
    assert "symbol=BTCUSDT; min_expectancy filter applied" in content
