from dataclasses import FrozenInstanceError

import pytest

from scalpbot.core.events import BookTop, Candle, Fill, Side


def test_events_are_immutable():
    c = Candle(
        symbol="ETH", open_time_ms=0, interval="1s",
        open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0,
    )
    with pytest.raises(FrozenInstanceError):
        c.close = 9.9  # type: ignore[misc]


def test_spread_bps():
    top = BookTop(symbol="ETH", ts_ms=0, bid_px=99.995, bid_sz=1.0, ask_px=100.005, ask_sz=1.0)
    assert top.spread_bps == pytest.approx(1.0, rel=1e-6)


def test_fill_rebate_sign_convention():
    # negative fee = rebate received (maker on Hyperliquid base tier)
    f = Fill(symbol="ETH", ts_ms=0, cloid="c1", side=Side.BUY,
             px=100.0, sz=1.0, is_maker=True, fee=-0.005)
    assert f.is_maker and f.fee < 0
