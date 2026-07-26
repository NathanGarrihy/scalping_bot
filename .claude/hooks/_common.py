"""Shared helpers for scalpbot Claude Code hooks (.claude/hooks/*.py).

Hook scripts are invoked standalone via the bare `py` launcher (fast, stdlib
only) — none of them need scalpbot's own dependencies to run their own logic.
Where a hook must invoke a project tool (ruff, pytest, the gate scripts'
python), it calls straight into scalpbot's .venv rather than assuming an
activated environment, since the hook's own invocation shell may not have one.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCALPBOT_ROOT = Path(__file__).resolve().parents[2]


def read_input() -> dict:
    """Claude Code invokes hooks via PowerShell on this machine, which prepends
    a UTF-8 BOM when piping a string to a native process's stdin. Plain
    json.load chokes on that BOM, so decode with utf-8-sig (strips it if
    present, no-ops if not) before parsing."""
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig")
        return json.loads(raw)
    except Exception:
        return {}


def block(reason: str) -> None:
    """PreToolUse: exit 2 denies the tool call and surfaces `reason` to Claude."""
    print(reason, file=sys.stderr)
    sys.exit(2)


def venv_tool(name: str) -> str:
    """Path to `name` inside scalpbot's .venv, falling back to a bare PATH
    lookup if the venv hasn't been created yet."""
    bindir = "Scripts" if os.name == "nt" else "bin"
    exe = f"{name}.exe" if os.name == "nt" else name
    path = SCALPBOT_ROOT / ".venv" / bindir / exe
    return str(path) if path.exists() else name
