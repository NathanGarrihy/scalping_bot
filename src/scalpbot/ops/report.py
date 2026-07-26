"""Report: live/shadow equity curve plotted against the Phase 0 Monte Carlo
bands (PLAN.md Phases 4–5 validation). Also compares realized stop slippage
vs the modeled haircut and realized maker-fill rate vs the hostile model's
grant rate — the two assumptions most likely to be optimistic.
"""

from __future__ import annotations

from pathlib import Path


def build_report(run_dir: Path, mc_bands_path: Path, out_html: Path) -> Path:
    raise NotImplementedError("Phase 4")
