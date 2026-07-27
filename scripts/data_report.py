"""Print (and save) the Task 0.1 data integrity/regime/cross-venue-basis
report over the real, already-ingested corpora (PLAN.md §3).

A human reads this output before hand-assessing `gates/gate0_edge.py`.

    uv run python scripts/data_report.py [--data-root data] [--config configs/research.yaml]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from scalpbot.data.config import load_data_config
from scalpbot.data.report import build_report, render_text

PILOT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config", default="configs/research.yaml")
    parser.add_argument("--symbols", default=",".join(PILOT_SYMBOLS))
    args = parser.parse_args()

    data_root = Path(args.data_root)
    cfg = load_data_config(args.config)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    report = build_report(data_root, cfg, symbols)
    text = render_text(report)
    print(text)

    reports_dir = data_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"integrity_report_{int(time.time())}.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"\n(saved to {out_path})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
