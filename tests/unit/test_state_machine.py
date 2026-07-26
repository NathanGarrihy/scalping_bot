import pytest

from scalpbot.core.state_machine import (
    TRANSITIONS,
    BotState,
    IllegalTransition,
    can_transition,
    transition,
)


def test_happy_path():
    path = [
        BotState.WAITING,
        BotState.SIGNAL_GENERATED,
        BotState.ORDER_PLACED,
        BotState.FILLED,
        BotState.MANAGING_POSITION,
        BotState.FLAT,
        BotState.WAITING,
    ]
    for src, dst in zip(path, path[1:], strict=False):
        assert transition(src, dst) is dst


def test_illegal_transition_raises():
    with pytest.raises(IllegalTransition):
        transition(BotState.WAITING, BotState.FILLED)


def test_halted_only_resumes_to_waiting():
    assert TRANSITIONS[BotState.HALTED] == frozenset({BotState.WAITING})


def test_every_state_can_halt_except_flat_and_halted():
    for state in BotState:
        if state in (BotState.FLAT, BotState.HALTED):
            assert not can_transition(state, BotState.HALTED)
        else:
            assert can_transition(state, BotState.HALTED)


def test_transition_table_covers_all_states():
    assert set(TRANSITIONS) == set(BotState)
