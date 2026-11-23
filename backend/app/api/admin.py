from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import Actor, get_client, get_notifier, get_session, require_permission
from app.core.permissions import Permission
from app.core.settings import get_settings
from app.providers.notify import Notifier
from app.schemas.admin import JurisdictionOut, StaffRowOut
from app.schemas.auth import CreateInvite, InviteCreated
from app.services import admin_read, auth_service
from app.services.audit import ClientInfo

router = APIRouter(prefix="/admin", tags=["admin"])

# One dependency object per permission, defined once (route scan reads the permission off it).
CAN_MANAGE_USERS = Depends(require_permission(Permission.USER_MANAGE))


@router.post("/invites", response_model=InviteCreated, status_code=201)
def create_invite(
    body: CreateInvite,
    actor: Actor = CAN_MANAGE_USERS,
    session: Session = Depends(get_session),
    notifier: Notifier = Depends(get_notifier),
    client: ClientInfo = Depends(get_client),
) -> InviteCreated:
    invite, token = auth_service.create_invite(
        session,
        actor_user=actor.user,
        actor_can_manage=actor.access.scope(session, Permission.USER_MANAGE),
        actor_is_super_admin=actor.is_super_admin,
        email=body.email,
        role=body.role,
        jurisdiction_id=body.jurisdiction_id,
        notifier=notifier,
        client=client,
    )
    s = get_settings()
    return InviteCreated(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at.isoformat(),
        invite_url=None if s.environment == "production" else f"{s.public_base_url}/invite/{token}",
    )


@router.get("/jurisdictions", response_model=list[JurisdictionOut])
def jurisdictions(
    actor: Actor = CAN_MANAGE_USERS, session: Session = Depends(get_session)
) -> list[JurisdictionOut]:
    """The areas the caller manages (granted areas and everything below them), for the invite form."""
    return admin_read.list_jurisdictions(session, actor.access)


@router.get("/staff", response_model=list[StaffRowOut])
def staff(actor: Actor = CAN_MANAGE_USERS, session: Session = Depends(get_session)) -> list[StaffRowOut]:
    """Staff with their role and area, plus invites not yet accepted."""
    return admin_read.list_staff(
        session, actor.access, show_invite_tokens=get_settings().environment != "production"
    )
