"""FastAPI dependencies: sessions, the signed-in actor, permission checks, rate limits, notifier.

Every route is either public (an explicit allow-list in tests/test_route_permissions.py) or depends on
`require_permission(...)` / `require_authenticated`. A test fails if a new route has neither."""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.db import get_session
from app.core.errors import AuthenticationFailed, PermissionDenied
from app.core.permissions import ROLE_PERMISSIONS, Permission, role_can
from app.core.ratelimit import limiter
from app.core.settings import get_settings
from app.models import AppUser, RoleAssignment
from app.models.enums import Role, UserKind
from app.providers.notify import ConsoleNotifier, Notifier, UnconfiguredNotifier
from app.services.access import Access
from app.services.audit import ClientInfo

_bearer = HTTPBearer(auto_error=False)

__all__ = [
    "Actor",
    "get_optional_actor",
    "get_client",
    "get_notifier",
    "get_session",
    "rate_limited",
    "require_authenticated",
    "require_permission",
]


@dataclass(frozen=True)
class Grant:
    role: str
    jurisdiction_id: uuid.UUID


@dataclass
class Actor:
    user: AppUser
    grants: list[Grant] = field(default_factory=list)

    @property
    def is_staff(self) -> bool:
        return self.user.kind is UserKind.STAFF

    def can(self, permission: Permission) -> bool:
        if not self.is_staff:
            return permission in ROLE_PERMISSIONS["viewer"]
        return any(role_can(g.role, permission) for g in self.grants)

    def jurisdiction_ids(self, permission: Permission) -> set[uuid.UUID]:
        """Jurisdictions where the actor holds a role that grants `permission`. Place queries must
        filter by this IN THE QUERY (M4), so out-of-scope rows are never loaded. Sub-areas of a granted
        state or district are expanded by the place service."""
        return {g.jurisdiction_id for g in self.grants if role_can(g.role, permission)}

    @property
    def is_super_admin(self) -> bool:
        return any(g.role == Role.SUPER_ADMIN.value for g in self.grants)

    @property
    def access(self) -> Access:
        """The framework-free view of this actor, which is what services receive."""
        return Access(
            user_id=self.user.id,
            is_staff=self.is_staff,
            name=self.user.name,
            grants=tuple((g.role, g.jurisdiction_id) for g in self.grants),
        )


def _valid_ip(host: str | None) -> str | None:
    """Only a real IP address can be stored in the audit log's inet column."""
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def get_client(request: Request) -> ClientInfo:
    return ClientInfo(
        ip=_valid_ip(request.client.host if request.client else None),
        request_id=request.headers.get("x-request-id") or uuid.uuid4().hex,
    )


@lru_cache
def _default_notifier() -> Notifier:
    return UnconfiguredNotifier() if get_settings().environment == "production" else ConsoleNotifier()


def get_notifier() -> Notifier:
    return _default_notifier()


def get_current_actor(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> Actor:
    if creds is None:
        raise AuthenticationFailed("Sign in to continue.")
    data = security.read_jwt(creds.credentials, "access")
    user = session.get(AppUser, uuid.UUID(data["sub"]))
    if not user or not user.is_active:
        raise AuthenticationFailed("Sign in to continue.")
    rows = session.scalars(select(RoleAssignment).where(RoleAssignment.user_id == user.id)).all()
    return Actor(user=user, grants=[Grant(r.role.value, r.jurisdiction_id) for r in rows])


def get_optional_actor(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> Actor | None:
    """For public routes that show more to a signed-in caller (the scan resolver). A missing or bad
    token simply means "anonymous"; it never errors."""
    if creds is None:
        return None
    try:
        return get_current_actor(creds, session)
    except AuthenticationFailed:
        return None


def require_authenticated(actor: Actor = Depends(get_current_actor)) -> Actor:
    return actor


require_authenticated.authenticated_only = True  # type: ignore[attr-defined]


def require_permission(permission: Permission) -> Callable[..., Actor]:
    def dependency(actor: Actor = Depends(get_current_actor)) -> Actor:
        if not actor.can(permission):
            raise PermissionDenied("You don't have permission to do that.")
        return actor

    dependency.required_permission = permission  # type: ignore[attr-defined]
    return dependency


def rate_limited(name: str, limit: int, window_seconds: int) -> Callable[..., None]:
    """Per client IP and route. In-process only: see app/core/ratelimit.py."""

    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        limiter.check(f"{name}:{ip}", limit, window_seconds)

    return dependency
