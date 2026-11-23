"""A small, realistic setup shared by the place/review/public tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core import security
from app.core.geo import LatLon
from app.models import AppUser, Jurisdiction, RoleAssignment
from app.models.enums import JurisdictionLevel, Role, UserKind
from tests.factories import make_jurisdiction, make_user

SUNRISE = LatLon(lat=12.971599, lon=77.594566)


def auth(user: AppUser) -> dict[str, str]:
    token = security.make_jwt("access", str(user.id), 15, kind=user.kind.value)
    return {"Authorization": f"Bearer {token}"}


@dataclass
class World:
    ka: Jurisdiction
    blr: Jurisdiction
    mys: Jurisdiction
    admin: AppUser
    registrar: AppUser
    registrar2: AppUser
    verifier: AppUser  # state-level grant: covers blr and mys
    printer: AppUser
    auditor: AppUser
    mys_registrar: AppUser
    mys_verifier: AppUser
    viewer: AppUser
    users: dict[str, AppUser] = field(default_factory=dict)

    def h(self, name: str) -> dict[str, str]:
        return auth(getattr(self, name))


def build_world(session) -> World:
    ka = make_jurisdiction(session, level=JurisdictionLevel.STATE)
    ka.name = "Karnataka"
    blr = make_jurisdiction(session, parent_id=ka.id)
    blr.name = "Bengaluru Urban"
    mys = make_jurisdiction(session, parent_id=ka.id)
    mys.name = "Mysuru"
    session.flush()

    def staff(role: Role, j: Jurisdiction, name: str) -> AppUser:
        # No real password or authenticator here (tests sign in with a minted token), which keeps
        # the fixture fast: password hashing is deliberately slow.
        user = make_user(session, UserKind.STAFF, name=name)
        session.add(RoleAssignment(user_id=user.id, role=role, jurisdiction_id=j.id))
        session.flush()
        return user

    return World(
        ka=ka,
        blr=blr,
        mys=mys,
        admin=staff(Role.ADMIN, blr, "Asha Admin"),
        registrar=staff(Role.REGISTRAR, blr, "Arun R."),
        registrar2=staff(Role.REGISTRAR, blr, "Meena S."),
        verifier=staff(Role.VERIFIER, ka, "Ravi M."),
        printer=staff(Role.PRINTER, blr, "Sunita K."),
        auditor=staff(Role.AUDITOR, blr, "Anil Auditor"),
        mys_registrar=staff(Role.REGISTRAR, mys, "Mysuru Registrar"),
        mys_verifier=staff(Role.VERIFIER, mys, "Mysuru Verifier"),
        viewer=make_user(session, UserKind.VIEWER, name="Vina Viewer"),
    )


def at(n: int = 0) -> dict[str, float]:
    """Points about 111 m apart, so the 15 m duplicate guard never fires between them."""
    return {"lat": round(SUNRISE.lat + 0.001 * n, 6), "lon": SUNRISE.lon}


def payload(n: int = 0, **kw):
    body = {
        "type": "building",
        "name": f"Test Court {n}",
        "geo": at(n),
        "accuracy_m": 5,
        "address": "12th Main",
        "landmark": "Opposite Metro",
        "locality": "Indiranagar",
        "postal_pin": "560038",
        "unit_labels": [],
    }
    return body | kw


def register(client, headers, n: int = 0, **kw) -> dict:
    r = client.post("/places", json=payload(n, **kw), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def approve(client, headers, place_id: str):
    return client.post(f"/places/{place_id}/decision", json={"decision": "approve"}, headers=headers)


def active_place(client, world, n: int = 0, **kw) -> dict:
    """A registered and verified place (registrar submits, the state verifier approves)."""
    p = register(client, world.h("registrar"), n, **kw)
    r = approve(client, world.h("verifier"), p["id"])
    assert r.status_code == 200, r.text
    return r.json()


def public_place(client, world, n: int = 0, **kw) -> dict:
    p = active_place(client, world, n, **kw)
    r = client.put(
        f"/places/{p['id']}/visibility",
        json={"visibility": "public", "consent_given_by": "Owner Name"},
        headers=world.h("verifier"),
    )
    assert r.status_code == 200, r.text
    return r.json()
