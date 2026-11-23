"""Role x endpoint matrix. 'Allowed' means the request got past the permission check (any status that is
not 401 or 403); 'denied' must be exactly 403; anonymous must be exactly 401."""

import pytest

from tests.world import auth, public_place

pytestmark = pytest.mark.db

STAFF = {"admin", "registrar", "verifier", "printer", "auditor"}
ROLES = ["viewer", *sorted(STAFF)]

# name -> (method, path template, body, roles allowed past the permission check)
ENDPOINTS = {
    "list places": ("get", "/places", None, STAFF),
    "nearby": ("get", "/places/nearby?lat=12.97&lon=77.59", None, STAFF),
    "create place": (
        "post",
        "/places",
        {"type": "house", "name": "H", "geo": {"lat": 13.1, "lon": 77.7}, "accuracy_m": 5},
        {"admin", "registrar"},
    ),
    "get place": ("get", "/places/{id}", None, STAFF),
    "update place": ("patch", "/places/{id}", {"name": "Renamed"}, {"admin", "registrar"}),
    "list units": ("get", "/places/{id}/units", None, STAFF),
    "add units": ("post", "/places/{id}/units", {"labels": ["Z1"]}, {"admin", "registrar"}),
    "history": ("get", "/places/{id}/history", None, STAFF),
    "visibility": (
        "put",
        "/places/{id}/visibility",
        {"visibility": "private"},
        {"admin", "registrar", "verifier"},
    ),
    "decision": ("post", "/places/{id}/decision", {"decision": "approve"}, {"admin", "verifier"}),
    "resubmit": ("post", "/places/{id}/resubmit", None, {"admin", "registrar"}),
    "label": ("get", "/places/{id}/label", None, {"admin", "printer"}),
    "review queue": ("get", "/review", None, {"admin", "verifier"}),
    "audit events": ("get", "/audit/events", None, {"admin", "auditor"}),
    "admin staff": ("get", "/admin/staff", None, {"admin"}),
    "admin jurisdictions": ("get", "/admin/jurisdictions", None, {"admin"}),
    "invite": (
        "post",
        "/admin/invites",
        {
            "email": "m@pinpoint.test",
            "role": "printer",
            "jurisdiction_id": "{blr}",
        },
        {"admin"},
    ),
    "report a problem": ("post", "/places/{id}/corrections", {"note": "Something is off"}, {"viewer"}),
}


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_role_by_endpoint(client, world, endpoint):
    method, template, body, allowed = ENDPOINTS[endpoint]
    place = public_place(client, world, 0)
    path = template.replace("{id}", place["id"])
    if body and "jurisdiction_id" in body:
        body = body | {"jurisdiction_id": str(world.blr.id)}
    anonymous = client.request(method, path, json=body)
    assert anonymous.status_code == 401, f"anonymous {endpoint}: {anonymous.status_code}"
    for role in ROLES:
        headers = auth(world.viewer) if role == "viewer" else world.h(role)
        status = client.request(method, path, json=body, headers=headers).status_code
        if role in allowed:
            assert status not in (401, 403), f"{role} should pass {endpoint}, got {status}"
        else:
            assert status == 403, f"{role} should be refused {endpoint}, got {status}"
