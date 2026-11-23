"""Read-only admin views: jurisdictions, staff with pending invites, and the audit log.
Every query is limited to the caller's jurisdictions (granted areas plus their sub-areas)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.permissions import Permission
from app.models import AppUser, AuditEvent, Invite, Jurisdiction, RoleAssignment
from app.models.enums import UserKind
from app.schemas.admin import AuditEventOut, AuditPage, JurisdictionOut, StaffRowOut
from app.services.access import Access

AUDIT_PAGE_MAX = 200


def list_jurisdictions(session: Session, who: Access) -> list[JurisdictionOut]:
    scope = who.scope(session, Permission.USER_MANAGE)
    rows = session.scalars(
        select(Jurisdiction).where(Jurisdiction.id.in_(scope)).order_by(Jurisdiction.level, Jurisdiction.name)
    )
    return [
        JurisdictionOut(id=j.id, name=j.name, code=j.code, level=j.level, parent_id=j.parent_id) for j in rows
    ]


def list_staff(session: Session, who: Access, *, show_invite_tokens: bool) -> list[StaffRowOut]:
    """Active staff (one row per role assignment) and invites still waiting to be accepted."""
    scope = who.scope(session, Permission.USER_MANAGE)
    rows: list[StaffRowOut] = []
    assigned = session.execute(
        select(RoleAssignment, AppUser, Jurisdiction.name)
        .join(AppUser, AppUser.id == RoleAssignment.user_id)
        .join(Jurisdiction, Jurisdiction.id == RoleAssignment.jurisdiction_id)
        .where(
            RoleAssignment.jurisdiction_id.in_(scope),
            AppUser.kind == UserKind.STAFF,
            AppUser.is_active.is_(True),
        )
        .order_by(AppUser.email)
    )
    for ra, user, jname in assigned:
        rows.append(
            StaffRowOut(
                id=ra.id,
                user_id=user.id,
                email=user.email or "",
                name=user.name,
                role=ra.role,
                jurisdiction_id=ra.jurisdiction_id,
                jurisdiction_name=jname,
                status="active",
            )
        )
    pending = session.execute(
        select(Invite, Jurisdiction.name)
        .join(Jurisdiction, Jurisdiction.id == Invite.jurisdiction_id)
        .where(
            Invite.jurisdiction_id.in_(scope),
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
        .order_by(Invite.created_at)
    )
    for invite, jname in pending:
        mine = show_invite_tokens and invite.invited_by == who.user_id
        rows.append(
            StaffRowOut(
                id=invite.id,
                user_id=None,
                email=invite.email,
                name="",
                role=invite.role,
                jurisdiction_id=invite.jurisdiction_id,
                jurisdiction_name=jname,
                status="invited",
                invite_token=security.invite_token(invite.id) if mine else None,
                invite_expires_at=invite.expires_at,
            )
        )
    return rows


def list_audit_events(
    session: Session,
    who: Access,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    before_id: int | None = None,
    limit: int = 50,
) -> AuditPage:
    """Newest first. Events with no jurisdiction (sign-ins, for example) are for super admins only."""
    scope = who.scope(session, Permission.AUDIT_READ)
    visible = AuditEvent.jurisdiction_id.in_(scope)
    if who.is_super_admin:
        visible = or_(visible, AuditEvent.jurisdiction_id.is_(None))
    stmt = (
        select(AuditEvent, AppUser.name, AppUser.kind)
        .outerjoin(AppUser, AppUser.id == AuditEvent.actor_id)
        .where(visible)
    )
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditEvent.resource_id == resource_id)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if before_id:
        stmt = stmt.where(AuditEvent.id < before_id)
    n = min(max(limit, 1), AUDIT_PAGE_MAX)
    found = session.execute(stmt.order_by(AuditEvent.id.desc()).limit(n + 1)).all()
    items = [
        AuditEventOut(
            id=ev.id,
            at=ev.at,
            actor_id=ev.actor_id,
            actor_name=None if name is None else (name if kind is UserKind.STAFF else "Normal user"),
            action=ev.action,
            resource_type=ev.resource_type,
            resource_id=ev.resource_id,
            jurisdiction_id=ev.jurisdiction_id,
            request_id=ev.request_id,
            detail=ev.detail,
        )
        for ev, name, kind in found[:n]
    ]
    return AuditPage(items=items, next_before_id=items[-1].id if len(found) > n and items else None)
