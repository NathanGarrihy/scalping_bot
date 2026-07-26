"""PreToolUse (Edit|Write): enforce core purity.

scalpbot.core must stay a pure function of (state, event, config) -> actions
(CLAUDE.md architecture rules). Blocks edits under src/scalpbot/core/ that
import a driver/venue module, or touch the clock, randomness, or I/O.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCALPBOT_ROOT, block, read_input  # noqa: E402

CORE_ROOT = SCALPBOT_ROOT / "src" / "scalpbot" / "core"

FORBIDDEN = [
    (
        re.compile(r"^\s*(from|import)\s+scalpbot\.(venues|live|data|backtest|ops)\b"),
        "imports a driver/venue module",
    ),
    (re.compile(r"\btime\.time\s*\("), "reads the wall clock (time.time)"),
    (re.compile(r"\bdatetime\.now\s*\("), "reads the wall clock (datetime.now)"),
    (re.compile(r"\brandom\.\w+\s*\("), "uses randomness (random module)"),
    (re.compile(r"(?<!\.)\bopen\s*\("), "performs file I/O (open())"),
    (re.compile(r"\brequests\.\w+\s*\("), "performs network I/O (requests)"),
    (re.compile(r"\bhttpx\.\w+\s*\("), "performs network I/O (httpx)"),
]


def scan(text: str) -> list[str]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        for pattern, desc in FORBIDDEN:
            if pattern.search(line):
                hits.append(f"  line {lineno}: {desc} -- {line.strip()}")
    return hits


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
    if not resolved.is_relative_to(CORE_ROOT):
        return 0

    text = tool_input.get("content")
    if text is None:
        text = tool_input.get("new_string", "")

    hits = scan(text)
    if hits:
        block(
            "BLOCKED by guard_core_purity: scalpbot.core must stay pure -- no "
            "I/O, clock reads, randomness, or venue/driver imports (CLAUDE.md "
            "architecture rules).\n"
            + "\n".join(hits)
            + "\nIf this is a false positive (inside a comment/string), ask the "
            "user to make this edit directly instead."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
