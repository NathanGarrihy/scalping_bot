"""PreToolUse (Bash): defense-in-depth secrets guard for git add/commit.

.gitignore already excludes .env, but this catches `git add -f` or key
material accidentally pasted into some other tracked file, before it enters
git history. General-purpose (not scalpbot-specific) since it fires on
whatever repo the Bash command's cwd actually points at.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import block, read_input  # noqa: E402

GIT_ADD_COMMIT = re.compile(r"\bgit\s+(add|commit)\b")
SECRET_PATTERNS = [
    re.compile(r"0x[0-9a-fA-F]{64}"),
    re.compile(r"(?i)\bPRIVATE_KEY\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bAGENT_PRIVATE_KEY\s*[:=]\s*\S+"),
]


def candidate_files(cwd: str, command: str) -> set[str]:
    files: set[str] = set()
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in status.stdout.splitlines():
            path = line[3:].strip().strip('"')
            if path:
                files.add(path)
        if "commit" in command:
            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            files.update(p for p in staged.stdout.splitlines() if p)
    except Exception:
        pass
    return files


def main() -> int:
    data = read_input()
    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not GIT_ADD_COMMIT.search(command):
        return 0

    cwd = data.get("cwd") or "."
    for rel in candidate_files(cwd, command):
        if Path(rel).name == ".env":
            block(
                f"BLOCKED by guard_secrets: {rel} would be staged/committed. "
                ".env must never enter git history."
            )
        full = Path(cwd) / rel
        if full.is_file():
            try:
                text = full.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    block(
                        f"BLOCKED by guard_secrets: {rel} contains what looks "
                        "like private key material. Remove it before committing."
                    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
