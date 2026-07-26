"""Shared gate plumbing. Gates fail closed: unimplemented, errored, or
missing-artifact gates all exit non-zero and print FAIL."""

from __future__ import annotations

import sys

PASS = 0
FAIL = 2


def fail(gate: str, reason: str) -> int:
    print(f"[{gate}] FAIL — {reason}")
    return FAIL


def ok(gate: str, detail: str) -> int:
    print(f"[{gate}] PASS — {detail}")
    return PASS


def run(gate: str, main) -> None:
    try:
        code = main()
    except NotImplementedError:
        code = fail(gate, "gate not implemented; gates fail closed")
    except Exception as exc:  # noqa: BLE001 — a crashed gate is a failed gate
        code = fail(gate, f"gate crashed: {exc!r}")
    sys.exit(code)
