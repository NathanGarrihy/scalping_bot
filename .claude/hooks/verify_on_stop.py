"""Stop: if any Python file is dirty in scalpbot's repo, run ruff + pytest and
surface failures so a regression never reaches the user silently.

Guards against an infinite loop via `stop_hook_active` (set by Claude Code
when this is already a continuation from a prior block by this same hook).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCALPBOT_ROOT, read_input, venv_tool  # noqa: E402


def dirty_python_files() -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(SCALPBOT_ROOT), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return any(line[3:].strip().endswith(".py") for line in result.stdout.splitlines())


def main() -> int:
    data = read_input()
    if data.get("stop_hook_active"):
        return 0  # already looping from a prior block -- let it stop this time

    if not dirty_python_files():
        return 0

    ruff = subprocess.run(
        [venv_tool("ruff"), "check"],
        cwd=SCALPBOT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    pytest = subprocess.run(
        [venv_tool("pytest"), "-q"],
        cwd=SCALPBOT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if ruff.returncode != 0 or pytest.returncode != 0:
        print(
            "verify_on_stop: Python changed this turn -- ruff/pytest failed:",
            file=sys.stderr,
        )
        if ruff.returncode != 0:
            print("--- ruff check ---", file=sys.stderr)
            print(ruff.stdout + ruff.stderr, file=sys.stderr)
        if pytest.returncode != 0:
            print("--- pytest -q ---", file=sys.stderr)
            print(pytest.stdout + pytest.stderr, file=sys.stderr)
        sys.exit(2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
