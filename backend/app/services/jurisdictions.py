"""Jurisdiction tree helpers (state > district > postal area)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Jurisdiction
from app.models.enums import JurisdictionLevel


def expand(session: Session, ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """The given jurisdictions and every descendant (recursive query, one round trip)."""
    start = set(ids)
    if not start:
        return set()
    tree = select(Jurisdiction.id).where(Jurisdiction.id.in_(start)).cte("tree", recursive=True)
    child = select(Jurisdiction.id).join(tree, Jurisdiction.parent_id == tree.c.id)
    tree = tree.union(child)
    return set(session.scalars(select(tree.c.id)))


def state_and_district(session: Session, jurisdiction_id: uuid.UUID) -> tuple[str, str]:
    """Names of the state and district above (or at) a jurisdiction, for the place's address fields."""
    state = district = ""
    current = session.get(Jurisdiction, jurisdiction_id)
    for _ in range(5):  # the tree is three levels deep; the bound guards against a bad cycle
        if current is None:
            break
        if current.level is JurisdictionLevel.STATE:
            state = current.name
        elif current.level is JurisdictionLevel.DISTRICT:
            district = current.name
        current = session.get(Jurisdiction, current.parent_id) if current.parent_id else None
    return state, district
