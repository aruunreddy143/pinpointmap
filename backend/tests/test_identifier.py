import pytest
from fastapi import APIRouter, Depends

from app.core.deps import require_permission
from app.core.permissions import Permission
from app.domain.identifier import Identifier, parse_identifier
from tests.test_route_permissions import _guard


@pytest.mark.parametrize(
    "text",
    ["98765 43210", "+91 98765-43210", "919876543210", "09876543210", "(98765) 43210", "9876543210"],
)
def test_all_the_ways_of_writing_one_mobile_number_normalize_the_same(text):
    assert parse_identifier(text) == Identifier("mobile", "+919876543210")


def test_email_is_lower_cased_and_trimmed():
    assert parse_identifier("  Priya@Example.COM ") == Identifier("email", "priya@example.com")


@pytest.mark.parametrize(
    "text", ["", "12345", "5876543210", "98765432101234", "priya@", "@example.com", "priya example", "abc"]
)
def test_anything_else_is_refused(text):
    assert parse_identifier(text) is None


def test_the_route_scan_helper_can_tell_guarded_from_unguarded():
    """Guards the guard: if _guard always said True, the route-permission test would prove nothing."""
    router = APIRouter()

    @router.get("/open")
    def open_route():
        return {}

    @router.get("/closed", dependencies=[Depends(require_permission(Permission.PLACE_READ))])
    def closed_route():
        return {}

    by_path = {r.path: r for r in router.routes}
    assert _guard(by_path["/open"].dependant) is False
    assert _guard(by_path["/closed"].dependant) is True
