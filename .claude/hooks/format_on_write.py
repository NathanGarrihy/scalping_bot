"""PostToolUse (Edit|Write): auto-format + lint-fix Python files immediately.

Every .py file scalpbot touches is ruff-clean the instant it's written --
removes manual formatting as a step entirely.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCALPBOT_ROOT, read_input, venv_tool  # noqa: E402


def main() -> int:
    try:
        data = read_input()
        file_path = data.get("tool_input", {}).get("file_path", "")
        if not file_path.endswith(".py"):
            return 0
        resolved = Path(file_path).resolve()
        if not resolved.is_relative_to(SCALPBOT_ROOT) or not resolved.exists():
            return 0

        ruff = venv_tool("ruff")
        subprocess.run([ruff, "format", str(resolved)], capture_output=True, timeout=30)
        subprocess.run(
            [ruff, "check", "--fix", "--quiet", str(resolved)],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
