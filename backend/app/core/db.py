from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import get_settings


class Base(DeclarativeBase):
    """All ORM models derive from this. The naming convention gives every constraint a stable name,
    which Alembic needs to change or drop it later."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def make_engine(url: str | None = None, **kwargs):
    return create_engine(url or get_settings().database_url, pool_pre_ping=True, **kwargs)


_SessionLocal: sessionmaker[Session] | None = None


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    global _SessionLocal  # noqa: PLW0603
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=make_engine(), expire_on_commit=False)
    with _SessionLocal() as session:
        yield session
