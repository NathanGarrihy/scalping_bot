"""One-command killswitch (PLAN.md Task 3.3): cancel-all, flatten, halt.

Must be usable from a phone over SSH:
    uv run python -m scalpbot.live.killswitch
No confirmation prompt — invoking it IS the confirmation. Writes a halt marker
the engine checks at boot so it stays down until explicitly resumed.
"""

from __future__ import annotations


async def fire() -> None:
    raise NotImplementedError("Phase 3 Task 3.3")


def main() -> None:
    raise NotImplementedError("Phase 3 Task 3.3")


if __name__ == "__main__":
    main()
