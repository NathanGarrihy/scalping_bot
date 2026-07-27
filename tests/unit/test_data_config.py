from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from scalpbot.data.config import DataConfig, load_data_config

VALID_YAML = """
data:
  signal_corpus:
    source: binance_archive
    interval: 1s
    start: "2024-07-01"
    end: "2026-06-30"
    holdout_months: 3
  venue_corpus:
    source: hyperliquid_archive
    start: "2026-01-01"

universe:
  volume_rank_max: 40
"""


def test_load_data_config_parses_real_research_yaml() -> None:
    cfg = load_data_config("configs/research.yaml")
    assert cfg.signal_corpus.source == "binance_archive"
    assert cfg.venue_corpus.source == "hyperliquid_archive"


def test_load_data_config_ignores_other_top_level_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "research.yaml"
    config_path.write_text(VALID_YAML, encoding="utf-8")

    cfg = load_data_config(config_path)

    assert cfg == DataConfig.model_validate(
        {
            "signal_corpus": {
                "source": "binance_archive",
                "interval": "1s",
                "start": "2024-07-01",
                "end": "2026-06-30",
                "holdout_months": 3,
            },
            "venue_corpus": {"source": "hyperliquid_archive", "start": "2026-01-01"},
        }
    )


def test_venue_corpus_end_defaults_to_none(tmp_path: Path) -> None:
    config_path = tmp_path / "research.yaml"
    config_path.write_text(VALID_YAML, encoding="utf-8")

    cfg = load_data_config(config_path)

    assert cfg.venue_corpus.end is None


def test_holdout_start_computed_from_end_minus_holdout_months() -> None:
    cfg = DataConfig.model_validate(
        {
            "signal_corpus": {
                "source": "binance_archive",
                "interval": "1s",
                "start": "2024-07-01",
                "end": "2026-06-30",
                "holdout_months": 3,
            },
            "venue_corpus": {"source": "hyperliquid_archive", "start": "2026-01-01"},
        }
    )

    # 3 whole months quarantined before end (2026-06-30): April, May, June.
    assert cfg.signal_corpus.holdout_start == date(2026, 4, 1)


def test_holdout_start_crosses_year_boundary() -> None:
    cfg = DataConfig.model_validate(
        {
            "signal_corpus": {
                "source": "binance_archive",
                "interval": "1s",
                "start": "2024-07-01",
                "end": "2026-01-31",
                "holdout_months": 3,
            },
            "venue_corpus": {"source": "hyperliquid_archive", "start": "2026-01-01"},
        }
    )

    # 3 whole months quarantined before end (2026-01-31): Nov, Dec, Jan.
    assert cfg.signal_corpus.holdout_start == date(2025, 11, 1)


def test_missing_data_block_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "research.yaml"
    config_path.write_text("universe:\n  volume_rank_max: 40\n", encoding="utf-8")

    with pytest.raises(KeyError):
        load_data_config(config_path)


def test_malformed_data_block_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "research.yaml"
    config_path.write_text(
        "data:\n  signal_corpus:\n    source: binance_archive\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_data_config(config_path)
