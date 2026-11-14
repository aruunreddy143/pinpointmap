import re
import uuid
from pathlib import Path

import pytest

from app.core.deps import Actor, Grant
from app.core.permissions import ROLE_PERMISSIONS, Permission, role_can
from app.models import AppUser
from app.models.enums import UserKind

P = Permission

EXPECTED = {
    "super_admin": {
        P.PLACE_READ,
        P.PLACE_CREATE,
        P.PLACE_UPDATE,
        P.PLACE_VERIFY,
        P.PLACE_PRINT,
        P.USER_MANAGE,
        P.AUDIT_READ,
    },
    "admin": {
        P.PLACE_READ,
        P.PLACE_CREATE,
        P.PLACE_UPDATE,
        P.PLACE_VERIFY,
        P.PLACE_PRINT,
        P.USER_MANAGE,
        P.AUDIT_READ,
    },
    "registrar": {P.PLACE_READ, P.PLACE_CREATE, P.PLACE_UPDATE},
    "verifier": {P.PLACE_READ, P.PLACE_VERIFY},
    "printer": {P.PLACE_READ, P.PLACE_PRINT},
    "auditor": {P.PLACE_READ, P.AUDIT_READ},
    "viewer": {P.PLACE_READ_PUBLIC, P.CORRECTION_REQUEST},
}


@pytest.mark.parametrize("role", EXPECTED)
@pytest.mark.parametrize("permission", list(Permission))
def test_full_role_permission_matrix(role, permission):
    assert role_can(role, permission) is (permission in EXPECTED[role])


def test_viewer_has_no_staff_permission_at_all():
    staff_only = set(Permission) - {P.PLACE_READ_PUBLIC, P.CORRECTION_REQUEST}
    assert not (ROLE_PERMISSIONS["viewer"] & staff_only)


def test_backend_and_frontend_permission_maps_agree():
    """frontend/src/lib/permissions.ts hides buttons by role; the backend enforces. They must match."""
    ts = (Path(__file__).parents[2] / "frontend" / "src" / "lib" / "permissions.ts").read_text(
        encoding="utf-8"
    )
    block = re.search(r"const MAP[^=]*=\s*\{(.*?)\n\}", ts, re.S).group(1)
    frontend: dict[str, set[str]] = {}
    for name, items in re.findall(r"(\w+):\s*\[([^\]]*)\]", block):
        frontend[name] = set(re.findall(r"'([^']+)'", items))
    backend = {role: {p.value for p in perms} for role, perms in ROLE_PERMISSIONS.items()}
    assert frontend == backend


def _actor(kind, *grants):
    user = AppUser(kind=kind)
    return Actor(user=user, grants=[Grant(role, jid) for role, jid in grants])


def test_actor_permissions_come_from_grants_and_jurisdiction_is_tracked():
    a, b = uuid.uuid4(), uuid.uuid4()
    actor = _actor(UserKind.STAFF, ("registrar", a), ("verifier", b))
    assert actor.can(P.PLACE_CREATE) and actor.can(P.PLACE_VERIFY)
    assert actor.jurisdiction_ids(P.PLACE_CREATE) == {a}
    assert actor.jurisdiction_ids(P.PLACE_VERIFY) == {b}
    assert actor.jurisdiction_ids(P.USER_MANAGE) == set()
    assert not actor.can(P.USER_MANAGE)


def test_a_staff_account_with_no_role_can_do_nothing():
    actor = _actor(UserKind.STAFF)
    assert not any(actor.can(p) for p in Permission)


def test_viewer_actors_get_the_fixed_viewer_set_regardless_of_grants():
    actor = _actor(UserKind.VIEWER, ("admin", uuid.uuid4()))  # a stray grant must not elevate a viewer
    assert actor.can(P.PLACE_READ_PUBLIC) and actor.can(P.CORRECTION_REQUEST)
    assert not actor.can(P.PLACE_READ) and not actor.can(P.USER_MANAGE)
