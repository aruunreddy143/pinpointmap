from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import NOW


class AuditEvent(Base):
    """Append-only audit log. Written in the same transaction as the change it records.
    Holds ids and field names, never personal data, so erasure requests never need to edit it."""

    __tablename__ = "audit_event"
    __table_args__ = (sa.Index("ix_audit_event_resource", "resource_type", "resource_id"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id"), index=True
    )
    action: Mapped[str] = mapped_column(sa.String(60))
    resource_type: Mapped[str] = mapped_column(sa.String(40))
    resource_id: Mapped[str | None] = mapped_column(sa.String(64))
    jurisdiction_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("jurisdiction.id"))
    ip: Mapped[str | None] = mapped_column(INET)
    request_id: Mapped[str | None] = mapped_column(sa.String(64))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
