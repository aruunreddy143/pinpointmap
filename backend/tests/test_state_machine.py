import itertools

import pytest

from app.domain.state_machine import (
    IllegalTransitionError,
    can_transition,
    needs_other_person,
    transition,
)
from app.domain.state_machine import (
    PlaceStatus as S,
)

LEGAL = {
    (S.DRAFT, S.PENDING),
    (S.PENDING, S.ACTIVE),
    (S.PENDING, S.REJECTED),
    (S.REJECTED, S.PENDING),
    (S.ACTIVE, S.RETIRED),
    (S.ACTIVE, S.MERGED),
    (S.ACTIVE, S.SPLIT),
}


@pytest.mark.parametrize("a,b", list(itertools.product(S, S)))
def test_full_transition_table(a, b):
    assert can_transition(a, b) is ((a, b) in LEGAL)


def test_illegal_transition_raises_with_a_readable_message():
    with pytest.raises(IllegalTransitionError, match="draft cannot become active"):
        transition(S.DRAFT, S.ACTIVE)


def test_terminal_states_have_no_way_out():
    for terminal in (S.RETIRED, S.MERGED, S.SPLIT):
        assert not any(can_transition(terminal, t) for t in S)


def test_four_eyes_applies_to_activation_and_to_end_of_life_moves():
    for target in (S.ACTIVE, S.RETIRED, S.MERGED, S.SPLIT):
        assert needs_other_person(target)
    for target in (S.PENDING, S.REJECTED, S.DRAFT):
        assert not needs_other_person(target)
