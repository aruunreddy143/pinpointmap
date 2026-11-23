"""Default deny: a new route must either require a permission / sign-in or be added, on purpose, to the
public allow-list below. Forgetting a permission check fails this test."""

import pytest
from fastapi.routing import APIRoute

from app.api import admin, audit, auth, places, public
from app.main import create_app

PUBLIC = {
    ("GET", "/health"),
    ("POST", "/auth/otp/request"),
    ("POST", "/auth/otp/verify"),
    ("POST", "/auth/otp/signup"),
    ("POST", "/auth/staff/login"),
    ("POST", "/auth/staff/totp"),
    ("POST", "/auth/refresh"),  # guarded by the refresh cookie + CSRF header
    ("POST", "/auth/logout"),
    ("POST", "/auth/password/forgot"),
    ("POST", "/auth/password/reset"),
    ("GET", "/auth/invites/{token}"),
    ("POST", "/auth/invites/{token}/accept"),
    # Public by design (rate limited; they show only what a place's visibility allows).
    ("GET", "/p/{code}"),
    ("GET", "/public/places"),
    ("GET", "/public/places/{ref}"),
}


ROUTERS = (auth.router, admin.router, places.router, places.review_router, audit.router, public.router)


def _all_routes() -> list[APIRoute]:
    app = create_app()
    own = [r for r in app.routes if isinstance(r, APIRoute)]
    return own + [r for router in ROUTERS for r in router.routes if isinstance(r, APIRoute)]


def _guard(dependant) -> bool:
    for dep in dependant.dependencies:
        call = dep.call
        if getattr(call, "required_permission", None) or getattr(call, "authenticated_only", False):
            return True
        if _guard(dep):
            return True
    return False


def _methods(route: APIRoute) -> list[str]:
    return sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"})


def test_the_scan_sees_every_route_the_app_serves():
    scanned = {route.path for route in _all_routes()}
    served = set(create_app().openapi()["paths"])
    assert served <= scanned, f"routes the scan cannot see: {served - scanned}"


def test_every_route_is_guarded_or_deliberately_public():
    unguarded = {(m, r.path) for r in _all_routes() if not _guard(r.dependant) for m in _methods(r)}
    assert unguarded == PUBLIC, (
        f"unexpectedly public: {unguarded - PUBLIC}; allow-listed but now guarded: {PUBLIC - unguarded}"
    )


@pytest.mark.db
def test_every_guarded_route_refuses_an_anonymous_caller(client):
    checked = 0
    for r in _all_routes():
        if not _guard(r.dependant):
            continue
        for m in _methods(r):
            path = r.path.replace("{", "x").replace("}", "")
            resp = client.request(m, path, json={})
            assert resp.status_code == 401, f"{m} {r.path} answered {resp.status_code} to an anonymous caller"
            checked += 1
    assert checked >= 15
