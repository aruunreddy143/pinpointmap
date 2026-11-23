"""Routes anyone can call: the scan resolver and the public place views. Rate limited so they cannot
be used to enumerate places. They show only what a place's visibility allows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import Actor, get_client, get_optional_actor, get_session, rate_limited
from app.schemas.places import PublicPlaceDetail, PublicPlaceOut, ResolveOut
from app.services import public
from app.services.audit import ClientInfo

router = APIRouter(tags=["public"])


@router.get(
    "/p/{code}",
    response_model=ResolveOut,
    dependencies=[Depends(rate_limited("resolve", 60, 60))],
)
def resolve(
    code: str,
    response: Response,
    actor: Actor | None = Depends(get_optional_actor),
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> ResolveOut:
    """The scan target. A bad check character is answered without touching the database.
    invalid and not_found come back as 404; everything else as 200 (see ResolveOut.kind)."""
    answer, status = public.resolve(session, actor.access if actor else None, code, client)
    response.status_code = status
    return answer


@router.get(
    "/public/places",
    response_model=list[PublicPlaceOut],
    dependencies=[Depends(rate_limited("public-search", 60, 60))],
)
def search(
    q: str = Query("", max_length=100), session: Session = Depends(get_session)
) -> list[PublicPlaceOut]:
    return public.search(session, q)


@router.get(
    "/public/places/{ref}",
    response_model=PublicPlaceDetail,
    dependencies=[Depends(rate_limited("public-place", 120, 60))],
)
def public_place(ref: str, session: Session = Depends(get_session)) -> PublicPlaceDetail:
    """A public, active place by its id or PINPOINT ID, with its units. Anything else is 404."""
    return public.public_place(session, ref)
