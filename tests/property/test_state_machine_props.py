"""Property tests for the execution state machine (PLAN.md Task 2.2)."""

from hypothesis import given
from hypothesis import strategies as st

from scalpbot.core.state_machine import (
    TRANSITIONS,
    BotState,
    IllegalTransition,
    can_transition,
    transition,
)

states = st.sampled_from(list(BotState))


@given(src=states, dst=states)
def test_transition_agrees_with_table(src: BotState, dst: BotState):
    if can_transition(src, dst):
        assert transition(src, dst) is dst
    else:
        try:
            transition(src, dst)
        except IllegalTransition as e:
            assert e.src is src and e.dst is dst
        else:
            raise AssertionError("expected IllegalTransition")


@given(src=states)
def test_no_self_loops(src: BotState):
    assert src not in TRANSITIONS[src]


@given(walk=st.lists(states, min_size=1, max_size=50))
def test_walks_never_skip_order_placement(walk: list[BotState]):
    """From any legal walk starting at WAITING, a position state is reachable
    only through ORDER_PLACED -> FILLED — there is no path into
    MANAGING_POSITION that bypasses an acknowledged fill."""
    state = BotState.WAITING
    prev = state
    for step in walk:
        if not can_transition(state, step):
            continue  # ignore illegal proposals, follow legal ones
        prev, state = state, step
        if state is BotState.MANAGING_POSITION:
            assert prev is BotState.FILLED
