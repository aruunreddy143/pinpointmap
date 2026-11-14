import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db


def test_postgis_is_available(db_session):
    assert db_session.execute(text("SELECT PostGIS_Version()")).scalar()


def test_distances_are_computed_in_metres_on_geography(db_session):
    # Two points 0.0001 degrees of latitude apart are about 11 m apart.
    metres = db_session.execute(
        text(
            "SELECT ST_Distance("
            "ST_SetSRID(ST_MakePoint(77.594566, 12.971599), 4326)::geography,"
            "ST_SetSRID(ST_MakePoint(77.594566, 12.971699), 4326)::geography)"
        )
    ).scalar()
    assert 10 < metres < 12
