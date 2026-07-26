"""PreToolUse (Edit): frozen-config discipline (PLAN.md section 10).

A strategy config marked `status: VALIDATED` is hash-pinned; changing it means
deliberately re-running the walk-forward protocol and re-freezing, not an
inline Edit from Claude.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCALPBOT_ROOT, block, read_input  # noqa: E402

SCOPE = SCALPBOT_ROOT / "configs" / "strategy"
VALIDATED_RE = re.compile(r"^\s*status:\s*VALIDATED\s*$", re.MULTILINE)


def main() -> int:
    data = read_input()
    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0
    try:
        resolved = Path(file_path).resolve()
    except Exception:
        return 0
    if not (resolved.is_relative_to(SCOPE) and resolved.suffix in (".yaml", ".yml")):
        return 0
    if not resolved.exists():
        return 0

    current = resolved.read_text(encoding="utf-8")
    if VALIDATED_RE.search(current):
        block(
            f"BLOCKED by guard_frozen_config: {resolved.name} is status: "
            "VALIDATED (hash-pinned per PLAN.md section 10). Re-running the "
            "walk-forward protocol and re-freezing is a deliberate action for "
            "the user to take directly, not an inline Edit."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
