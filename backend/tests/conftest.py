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
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.db import get_session, make_engine
from app.core.deps import get_notifier
from app.core.ratelimit import limiter
from app.core.settings import get_settings
from app.main import create_app
from app.providers.notify import OutboxNotifier

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


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def outbox() -> OutboxNotifier:
    return OutboxNotifier()


@pytest.fixture
def client(db_session, outbox) -> Iterator[TestClient]:
    """The real app, wired to the rolled-back test session and an in-memory outbox instead of SMS/email."""
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_notifier] = lambda: outbox
    with TestClient(app) as c:
        yield c


@pytest.fixture
def world(db_session):
    """Two districts under one state, and staff in each. The verifier holds a STATE grant, which must
    cover both districts (sub-area expansion)."""
    from tests.world import build_world

    return build_world(db_session)
