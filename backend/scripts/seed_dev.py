r"""Seed a local dev database so the real screens have data. Safe to re-run. Refuses to run in production.

    .venv\Scripts\python scripts/seed_dev.py

Creates: Karnataka > Bengaluru Urban, Mysuru, Mangaluru; staff logins (all use the same dev password,
printed with their authenticator keys); and demo places that mirror frontend/src/mocks/data.ts
(buildings with units, pending items for the review queue, a public place, a possible duplicate).
Coordinates are real points in Bengaluru; IDs are real (DIGIPIN cell + suffix + check character).
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.db import make_engine
from app.core.geo import LatLon, point
from app.core.settings import get_settings
from app.domain import place_id
from app.models import (
    AppUser,
    ConsentRecord,
    Jurisdiction,
    Place,
    PlaceEvent,
    RoleAssignment,
)
from app.models.enums import (
    JurisdictionLevel,
    LocationSource,
    PlaceStatus,
    PlaceType,
    Role,
    UserKind,
    Visibility,
)
from app.services import jurisdictions

PASSWORD = "Passw0rd!xyz"  # noqa: S105 (local dev only)
NOW = datetime.now(timezone.utc)


# ---------- jurisdictions ----------
def jurisdiction(
    s: Session, code: str, name: str, level: JurisdictionLevel, parent: Jurisdiction | None
) -> Jurisdiction:
    j = s.scalar(select(Jurisdiction).where(Jurisdiction.code == code))
    if j is None:
        j = Jurisdiction(code=code, name=name, level=level)
        s.add(j)
    j.name, j.level, j.parent_id = name, level, parent.id if parent else None
    s.flush()
    return j


# ---------- staff ----------
@dataclass
class Login:
    email: str
    name: str
    role: Role
    where: str
    secret: str


def staff(s: Session, email: str, name: str, role: Role, j: Jurisdiction) -> tuple[AppUser, Login]:
    user = s.scalar(select(AppUser).where(func.lower(AppUser.email) == email))
    if user is None:
        secret = security.new_totp_secret()
        user = AppUser(
            kind=UserKind.STAFF,
            email=email,
            name=name,
            password_hash=security.hash_password(PASSWORD),
            totp_secret=security.encrypt_secret(secret),
        )
        s.add(user)
        s.flush()
    else:
        secret = security.decrypt_secret(user.totp_secret or "")
    has_role = s.scalar(
        select(func.count()).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.role == role,
            RoleAssignment.jurisdiction_id == j.id,
        )
    )
    if not has_role:
        s.add(RoleAssignment(user_id=user.id, role=role, jurisdiction_id=j.id))
    s.flush()
    return user, Login(email, user.name, role, j.name, secret)


# ---------- demo places (mirrors frontend/src/mocks/data.ts) ----------
@dataclass
class Seed:
    name: str
    type: str
    lat: float
    lon: float
    address: str
    landmark: str
    locality: str
    pin: str
    status: PlaceStatus
    visibility: Visibility
    accuracy: float
    units: int
    by: str  # "arun" | "meena"
    age: timedelta
    district: str = "BLR-U"


A = PlaceStatus.ACTIVE
PEND = PlaceStatus.PENDING
PRIV, PUB = Visibility.PRIVATE, Visibility.PUBLIC

SEEDS = [
    Seed(
        "Sunrise Apartments",
        "building",
        12.971599,
        77.594566,
        "12th Main",
        "Opposite Metro Station, Gate 2",
        "Indiranagar",
        "560038",
        A,
        PUB,
        4,
        48,
        "arun",
        timedelta(days=5),
    ),
    Seed(
        "Sunrise Villa",
        "house",
        12.971699,
        77.594566,
        "12th Main",
        "Next to Sunrise Apartments",
        "Indiranagar",
        "560038",
        A,
        PUB,
        5,
        0,
        "arun",
        timedelta(days=6),
    ),
    Seed(
        "Lakeview Residency",
        "building",
        12.9698,
        77.7499,
        "Lake Road",
        "Near Forum Mall",
        "Whitefield",
        "560066",
        PEND,
        PRIV,
        6,
        24,
        "arun",
        timedelta(days=2),
    ),
    Seed(
        "14, 3rd Cross",
        "house",
        12.9308,
        77.5838,
        "14, 3rd Cross",
        "Behind Shopping Complex",
        "Jayanagar",
        "560011",
        PEND,
        PRIV,
        8,
        0,
        "meena",
        timedelta(days=2),
    ),
    # Moved about 9 m from Orchid Residency so the review queue shows a possible duplicate.
    Seed(
        "Green Court",
        "building",
        12.92798,
        77.6271,
        "27th Main",
        "Opposite Park",
        "HSR Layout",
        "560102",
        PEND,
        PRIV,
        7,
        60,
        "meena",
        timedelta(days=1),
    ),
    Seed(
        "7, Temple Road",
        "house",
        13.0035,
        77.5707,
        "7, Temple Road",
        "Near Temple",
        "Malleshwaram",
        "560003",
        PEND,
        PRIV,
        10,
        0,
        "meena",
        timedelta(days=1),
    ),
    Seed(
        "Palm Heights",
        "building",
        12.9352,
        77.6245,
        "5th Block",
        "Near Water Tank",
        "Koramangala",
        "560095",
        PEND,
        PRIV,
        5,
        18,
        "arun",
        timedelta(hours=5),
    ),
    Seed(
        "Orchid Residency",
        "building",
        12.9279,
        77.6271,
        "6th Block",
        "Opposite School",
        "Koramangala",
        "560095",
        A,
        PRIV,
        4,
        18,
        "arun",
        timedelta(days=9),
    ),
    Seed(
        "22, Lake View Road",
        "house",
        12.9857,
        77.7093,
        "22, Lake View Road",
        "Near Bridge",
        "Marathahalli",
        "560037",
        A,
        PRIV,
        6,
        0,
        "meena",
        timedelta(days=12),
    ),
    Seed(
        "Palace View House",
        "house",
        12.3052,
        76.6552,
        "3, Palace Road",
        "Near the palace gate",
        "Mysuru",
        "570001",
        A,
        PRIV,
        5,
        0,
        "meena",
        timedelta(days=4),
        district="MYS",
    ),
]


def _exists(s: Session):
    return lambda c: bool(s.scalar(select(func.count()).where(Place.public_id == c)))


def seed_place(
    s: Session, seed: Seed, users: dict[str, AppUser], verifier: AppUser, areas: dict[str, Jurisdiction]
) -> int:
    if s.scalar(select(func.count()).where(Place.name == seed.name, Place.parent_id.is_(None))):
        return 0
    j = areas[seed.district]
    state, district = jurisdictions.state_and_district(s, j.id)
    creator = users[seed.by]
    created = NOW - seed.age
    verified = seed.status is A
    geo = LatLon(lat=seed.lat, lon=seed.lon)

    def make(**kw) -> Place:
        return Place(
            id=uuid.uuid4(),
            geometry=point(geo),
            accuracy_m=seed.accuracy,
            location_source=LocationSource.GPS,
            address_text=seed.address,
            landmark=seed.landmark,
            locality=seed.locality,
            district=district,
            state=state,
            postal_pin=seed.pin,
            jurisdiction_id=j.id,
            visibility=seed.visibility,
            created_by=creator.id,
            created_at=created,
            updated_at=created,
            **kw,
        )

    def verify(p: Place, status: PlaceStatus) -> None:
        p.status = status
        p.verified_at = created + timedelta(days=1) if status is A else None
        p.verified_by = verifier.id if status is A else None

    parent = make(
        type=PlaceType(seed.type), name=seed.name, public_id=place_id.generate(seed.lat, seed.lon, _exists(s))
    )
    verify(parent, seed.status)
    s.add(parent)
    s.flush()
    taken: set[str] = set()
    n_units = 0
    for i in range(seed.units):
        floor = i // 4 + 1
        label = f"{floor}0{i % 4 + 1}"
        unit_status = seed.status
        if seed.name == "Sunrise Apartments":  # as in the mock: one unit still waiting, one retired
            unit_status = PEND if i == 3 else PlaceStatus.RETIRED if i == 6 else seed.status
        unit = make(
            type=PlaceType.UNIT,
            parent_id=parent.id,
            label=label,
            name=f"{seed.name}, {label}",
            public_id=place_id.generate(seed.lat, seed.lon, lambda c: c in taken or _exists(s)(c)),
        )
        taken.add(unit.public_id or "")
        verify(unit, unit_status)
        s.add(unit)
        n_units += 1
    s.flush()

    def event(
        kind: str, actor: AppUser, at: datetime, after: dict | None = None, reason: str | None = None
    ) -> None:
        s.add(PlaceEvent(place_id=parent.id, type=kind, actor_id=actor.id, at=at, after=after, reason=reason))

    event("submitted", creator, created, {"type": seed.type, "count": n_units})
    if verified:
        event("verified", verifier, created + timedelta(days=1), {"status": "active", "count": n_units})
    if seed.name == "Sunrise Apartments":
        event("pin_moved", creator, created + timedelta(hours=3), {"moved_m": 3})
        event("units_added", creator, created + timedelta(hours=1), {"count": 1})
        event("visibility_changed", verifier, created + timedelta(days=2), {"visibility": "public"})
        event("label_printed", users["admin"], NOW - timedelta(hours=2), {"format": "pdf"})
    if seed.visibility is PUB:
        s.add(
            ConsentRecord(
                place_id=parent.id,
                given_by_name="Demo owner",
                fields=["name", "address", "location"],
                recorded_by=verifier.id,
            )
        )
    return 1 + n_units


def main() -> int:
    if get_settings().environment == "production":
        print("Refusing to seed a production database.")
        return 1
    logins: list[Login] = []
    with Session(make_engine()) as s:
        ka = jurisdiction(s, "KA", "Karnataka", JurisdictionLevel.STATE, None)
        blr = jurisdiction(s, "BLR-U", "Bengaluru Urban", JurisdictionLevel.DISTRICT, ka)
        mys = jurisdiction(s, "MYS", "Mysuru", JurisdictionLevel.DISTRICT, ka)
        mng = jurisdiction(s, "MNG", "Mangaluru", JurisdictionLevel.DISTRICT, ka)
        areas = {"BLR-U": blr, "MYS": mys, "MNG": mng}

        admin, login = staff(s, "admin@pinpoint.test", "Dev Admin", Role.ADMIN, blr)
        logins.append(login)
        arun, login = staff(s, "registrar@pinpoint.test", "Arun R.", Role.REGISTRAR, blr)
        logins.append(login)
        meena, login = staff(s, "registrar2@pinpoint.test", "Meena S.", Role.REGISTRAR, blr)
        logins.append(login)
        ravi, login = staff(s, "verifier@pinpoint.test", "Ravi M.", Role.VERIFIER, ka)  # a STATE grant
        logins.append(login)
        _, login = staff(s, "auditor@pinpoint.test", "Anita Auditor", Role.AUDITOR, ka)
        logins.append(login)

        users = {"arun": arun, "meena": meena, "admin": admin}
        created = sum(seed_place(s, seed, users, ravi, areas) for seed in SEEDS)
        s.commit()

    print(f"Dev password for every login below: {PASSWORD}\n")
    for lg in logins:
        print(f"{lg.email:<28} {lg.role.value:<10} {lg.where:<16} TOTP key: {lg.secret}")
    print(f"\nPlaces created this run: {created} (0 means they already existed)")
    print("Normal users sign in with an email or mobile number and a code printed in the API console.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
