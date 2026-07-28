"""Append-only writer for `research/ledger.md` (PLAN.md §3, CLAUDE.md).

Every configuration ever evaluated — screens, failures, "just checking" —
gets a row here, per the ledger's own header and CLAUDE.md's "every research
experiment gets a row ... including failures." The trial count this produces
feeds `walkforward.py::deflated_expectancy`'s multiple-testing discount later;
an incomplete ledger silently inflates the edge.

Named `research_ledger.py` (not `ledger.py`) to avoid any collision with the
unrelated `shadow/ledger.py` (the Phase 4 paper-trade ledger) — different
concept entirely, just an unfortunate near-homonym.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from scalpbot.core.strategy import StrategyConfig

DEFAULT_LEDGER_PATH = Path("research/ledger.md")

_HEADER = """# Research Ledger

Append-only. Every configuration ever evaluated gets a row — including screens,
including failures, including "just checking". The trial count feeds the
multiple-testing discount in `backtest/walkforward.py::deflated_expectancy`;
an incomplete ledger silently inflates the edge. Interventions during live
phases are logged here too.

| Date (UTC) | Config hash | Data range | Splits | Result (expectancy R, trades) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""


def config_hash(config: StrategyConfig) -> str:
    """Stable short hash of a config's economically-relevant fields.

    `name` is deliberately excluded: two runs of the same parameters under
    different names must still be recognized as the same trial for the
    multiple-testing discount, or renaming a config would silently reset it.
    """
    payload = {
        "timeframe": config.timeframe,
        "bollinger": config.bollinger.model_dump(),
        "rsi": config.rsi.model_dump(),
        "exits": config.exits,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:12]


def append_row(
    *,
    config: StrategyConfig,
    symbol: str,
    data_range: str,
    splits: str,
    expectancy_r: float,
    n_trades: int,
    notes: str = "",
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
) -> None:
    """Appends one row to the ledger, creating it (with header) if missing.

    Never overwrites existing content — a missing/empty file gets the header
    written first, otherwise the row is appended as-is.
    """
    path = Path(ledger_path)
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_HEADER, encoding="utf-8")

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    full_notes = f"symbol={symbol}" + (f"; {notes}" if notes else "")
    row = (
        f"| {date} | {config_hash(config)} | {data_range} | {splits} | "
        f"{expectancy_r:.4f}R, {n_trades} | {full_notes} |\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(row)
