"""PreToolUse (Edit|Write): uv.lock is machine-generated. Direct edits drift
silently out of sync with pyproject.toml -- regenerate with `uv lock`/`uv
sync` instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCALPBOT_ROOT, block, read_input  # noqa: E402

TARGET = SCALPBOT_ROOT / "uv.lock"


def main() -> int:
    data = read_input()
    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0
    try:
        resolved = Path(file_path).resolve()
    except Exception:
        return 0
    if resolved == TARGET:
        block(
            "BLOCKED by guard_lockfile: uv.lock is machine-generated. Run "
            "`uv lock` or `uv sync` via Bash instead of hand-editing it."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
