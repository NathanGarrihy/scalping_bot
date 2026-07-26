"""Deterministic strategy core: pure functions of (state, event, config) -> actions.

Hard rules (CLAUDE.md): no I/O, no clock reads, no randomness, no venue imports.
This package is executed verbatim by the backtest replayer (Phase 0), the shadow
engine (Phase 4), and the live engine (Phase 5).
"""
