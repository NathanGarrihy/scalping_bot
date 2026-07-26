"""Chaos harness (PLAN.md Task 1.3 validation): spawn the engine against a mock
venue, kill -9 it mid-trade at randomized points, restart, and assert the
reconciled state is correct — no duplicated orders, no stopless positions.
Arrives with the journal (Phase 1)."""

import pytest

pytestmark = pytest.mark.skip(reason="blocked on Phase 1 Task 1.3: journal unimplemented")


def test_kill9_mid_trade_recovers():
    raise NotImplementedError
