"""Place lifecycle (see .claude/skills/pinpoint-registration-workflow).

draft -> pending_verification -> active -> retired | merged | split
                |
                v
             rejected -> pending_verification (after edits)
"""

from __future__ import annotations

from enum import Enum


class PlaceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending_verification"
    ACTIVE = "active"
    REJECTED = "rejected"
    RETIRED = "retired"
    MERGED = "merged"
    SPLIT = "split"


class IllegalTransitionError(ValueError):
    """Maps to HTTP 409 at the API boundary."""

    def __init__(self, current: PlaceStatus, target: PlaceStatus) -> None:
        super().__init__(f"A place that is {current.value} cannot become {target.value}.")
        self.current = current
        self.target = target


_ALLOWED: dict[PlaceStatus, frozenset[PlaceStatus]] = {
    PlaceStatus.DRAFT: frozenset({PlaceStatus.PENDING}),
    PlaceStatus.PENDING: frozenset({PlaceStatus.ACTIVE, PlaceStatus.REJECTED}),
    PlaceStatus.REJECTED: frozenset({PlaceStatus.PENDING}),
    PlaceStatus.ACTIVE: frozenset({PlaceStatus.RETIRED, PlaceStatus.MERGED, PlaceStatus.SPLIT}),
    PlaceStatus.RETIRED: frozenset(),
    PlaceStatus.MERGED: frozenset(),
    PlaceStatus.SPLIT: frozenset(),
}

# Moves that must be approved by someone other than the requester.
FOUR_EYES = frozenset({PlaceStatus.ACTIVE, PlaceStatus.RETIRED, PlaceStatus.MERGED, PlaceStatus.SPLIT})


def can_transition(current: PlaceStatus, target: PlaceStatus) -> bool:
    return target in _ALLOWED[current]


def transition(current: PlaceStatus, target: PlaceStatus) -> PlaceStatus:
    if not can_transition(current, target):
        raise IllegalTransitionError(current, target)
    return target


def needs_other_person(target: PlaceStatus) -> bool:
    return target in FOUR_EYES
