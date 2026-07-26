"""Deadman watchdog (PLAN.md Task 3.3) — runs as an INDEPENDENT process
(separate systemd unit, deploy/systemd/scalpbot-watchdog.service).

Watches the engine heartbeat file; on silence beyond `flatten_after_s` it
cancels all orders and flattens all positions via its own minimal venue
client. Kill criterion: sharing a failure domain with the engine.

Run: uv run python -m scalpbot.live.watchdog --config configs/live.yaml
"""

from __future__ import annotations

from pathlib import Path


async def watch(config_path: Path) -> None:
    raise NotImplementedError("Phase 3 Task 3.3")


def main() -> None:
    raise NotImplementedError("Phase 3 Task 3.3")


if __name__ == "__main__":
    main()
