import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

import app.models  # noqa: F401  (registers tables on Base.metadata)
from app.core.db import Base
from tests.conftest import alembic_config

pytestmark = pytest.mark.db


def test_migrations_can_go_down_and_up_again(db_engine, test_db_url):
    cfg = alembic_config(test_db_url)
    try:
        command.downgrade(cfg, "0001")
        with db_engine.connect() as conn:
            tables = {
                r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            }
            funcs = {
                r[0]
                for r in conn.execute(
                    text("SELECT proname FROM pg_proc WHERE proname='pinpoint_forbid_change'")
                )
            }
        assert "place" not in tables and not funcs
    finally:
        command.upgrade(cfg, "head")
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('public.place')")).scalar() == "place"


def test_models_and_migrations_agree(db_engine):
    """If a model changes without a migration (or the other way round), this fails."""

    def include(obj, name, type_, reflected, compare_to):  # noqa: ANN001
        return not (type_ == "table" and name == "spatial_ref_sys")

    with db_engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"include_object": include})
        diff = compare_metadata(ctx, Base.metadata)
    # Filter noise Alembic cannot compare (expression/partial indexes are created by hand-written SQL).
    real = [d for d in diff if not _is_known_noise(d)]
    assert real == [], real


def _is_known_noise(d) -> bool:
    items = d if isinstance(d, list) else [d]
    for item in items:
        kind = item[0]
        obj = item[1]
        name = getattr(obj, "name", "") or ""
        if kind in {"add_index", "remove_index"} and name in {
            "ix_place_geography",
            "uq_place_unit_label",
            "uq_app_user_email_lower",
        }:
            continue
        return False
    return True
