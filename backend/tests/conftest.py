"""Test fixtures. Integration tests use a REAL PostGIS database (docker compose up -d db); only
external services (SMS, email) are ever faked. Tests that need the database are skipped, with a
clear reason, when it is not reachable.

The test database is brought to the latest migration once per run, so tests exercise the real
schema (constraints, triggers, indexes), not a copy built from the models."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.db import make_engine
from app.core.settings import get_settings

ROOT = Path(__file__).parents[1]


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture(scope="session")
def test_db_url() -> str:
    return get_settings().test_database_url


@pytest.fixture(scope="session")
def db_engine(test_db_url):
    engine = make_engine(test_db_url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT PostGIS_Version()"))
    except OperationalError as exc:
        pytest.skip(
            f"PostGIS test database not reachable ({exc.__class__.__name__}). Run: docker compose up -d db"
        )
    command.upgrade(alembic_config(test_db_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Iterator[Session]:
    """Each test runs inside a transaction that is rolled back, so tests never see each other's data."""
    conn = db_engine.connect()
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        conn.close()
