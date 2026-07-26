"""SessionStart: surface phase-gate status every session.

PLAN.md section 9 says no infra/live work until the prior gate passes -- this
makes that rule live in context instead of relied-upon from memory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCALPBOT_ROOT, venv_tool  # noqa: E402

GATES = [
    "gate0_edge.py",
    "gate0_drawdown.py",
    "gate1_infra.py",
    "gate4_shadow.py",
    "gate5_live.py",
]


def main() -> int:
    lines = ["scalpbot phase-gate status (PLAN.md section 9):"]
    first_fail = None
    python = venv_tool("python")
    for gate in GATES:
        path = SCALPBOT_ROOT / "gates" / gate
        try:
            result = subprocess.run(
                [python, str(path)],
                cwd=SCALPBOT_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            status = "PASS" if result.returncode == 0 else "FAIL"
        except Exception as exc:  # noqa: BLE001
            status = f"FAIL (error: {exc!r})"
        lines.append(f"  {gate}: {status}")
        if status != "PASS" and first_fail is None:
            first_fail = gate

    if first_fail:
        lines.append(
            f"-> First unpassed gate: {first_fail}. Per PLAN.md, do not build "
            "infra/execution/live code for phases beyond this gate until it passes."
        )
    else:
        lines.append("-> All gates PASS.")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
