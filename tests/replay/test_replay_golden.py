"""Golden replay tests: identical event streams must produce identical action
streams across backtest/shadow/live drivers. Arrive with the backtest engine
(Phase 0 Task 0.3)."""

import pytest

pytestmark = pytest.mark.skip(reason="blocked on Phase 0 gate: core.strategy.decide unimplemented")


def test_golden_stream_determinism():
    raise NotImplementedError
