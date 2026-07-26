"""Asyncio live engine: adapter.stream_events() -> core.decide() -> adapter calls.

Boot sequence (refuses to start if any step fails):
1. Load configs/live.yaml; verify strategy config hash == frozen VALIDATED hash
   and no null gate-derived fields remain (PLAN.md §10 frozen-config discipline).
2. reconcile.py: journal vs exchange truth.
3. Subscribe streams; start heartbeat for the watchdog.

Run: uv run python -m scalpbot.live.engine --config configs/live.yaml
"""

from __future__ import annotations

from pathlib import Path


async def run(config_path: Path) -> None:
    raise NotImplementedError("blocked on Phase 0–2 gates")


def main() -> None:
    raise NotImplementedError("blocked on Phase 0–2 gates")


if __name__ == "__main__":
    main()
