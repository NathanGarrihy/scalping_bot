"""PreToolUse (Edit|Write): the network: field in configs/live.yaml is the
single highest-stakes switch in the system (real capital, Phase 5 burn-in,
PLAN.md section 8). The user flips it to mainnet directly -- never Claude.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCALPBOT_ROOT, block, read_input  # noqa: E402

TARGET = SCALPBOT_ROOT / "configs" / "live.yaml"
MAINNET_RE = re.compile(r"^\s*network:\s*mainnet\s*$", re.MULTILINE | re.IGNORECASE)


def main() -> int:
    data = read_input()
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0
    try:
        resolved = Path(file_path).resolve()
    except Exception:
        return 0
    if resolved != TARGET:
        return 0

    proposed = tool_input.get("content")
    if proposed is None:
        proposed = tool_input.get("new_string", "")

    if MAINNET_RE.search(proposed):
        block(
            "BLOCKED by guard_mainnet_switch: configs/live.yaml network: "
            "mainnet is a real-capital switch (Phase 5 burn-in, PLAN.md "
            "section 8). The user must make this change directly -- ask them "
            "to edit it themselves."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
