from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import JurisdictionLevel, OtpChannel, Role, UserKind, enum_column_type

NOW = sa.text("now()")


class Jurisdiction(Base):
    """State, district or postal (PIN) area. Role assignments and places are scoped to these."""

    __tablename__ = "jurisdiction"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level: Mapped[JurisdictionLevel] = mapped_column(
        enum_column_type(JurisdictionLevel, "jurisdiction_level")
    )
    name: Mapped[str] = mapped_column(sa.String(120))
    code: Mapped[str] = mapped_column(sa.String(32), unique=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("jurisdiction.id"), index=True)


class AppUser(Base):
    """Staff and normal (viewer) users. Mobile numbers are stored only as a keyed hash."""

    __tablename__ = "app_user"
    __table_args__ = (
        sa.CheckConstraint("kind <> 'staff' OR email IS NOT NULL", name="staff_has_email"),
        sa.CheckConstraint(
            "kind <> 'viewer' OR email IS NOT NULL OR mobile_hash IS NOT NULL", name="viewer_has_identifier"
        ),
        sa.CheckConstraint(
            "kind <> 'staff' OR password_hash IS NOT NULL OR NOT is_active", name="active_staff_has_password"
        ),
        sa.Index("uq_app_user_email_lower", sa.text("lower(email)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[UserKind] = mapped_column(enum_column_type(UserKind, "user_kind"))
    email: Mapped[str | None] = mapped_column(sa.String(254))
    mobile_hash: Mapped[str | None] = mapped_column(sa.String(128), unique=True)
    name: Mapped[str] = mapped_column(sa.String(120), default="")
    password_hash: Mapped[str | None] = mapped_column(sa.String(255))
    totp_secret: Mapped[str | None] = mapped_column(sa.String(255))  # encrypted at the application layer (M3)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    failed_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)

    roles: Mapped[list[RoleAssignment]] = relationship(
        back_populates="user", foreign_keys="RoleAssignment.user_id"
    )


class RoleAssignment(Base):
    """(user, role, jurisdiction). Authorisation is checked against this, in the query itself."""

    __tablename__ = "role_assignment"
    __table_args__ = (sa.UniqueConstraint("user_id", "role", "jurisdiction_id", name="uq_role_assignment"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("app_user.id"), index=True)
    role: Mapped[Role] = mapped_column(enum_column_type(Role, "role"))
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("jurisdiction.id"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)

    user: Mapped[AppUser] = relationship(back_populates="roles", foreign_keys=[user_id])


class Invite(Base):
    """A staff invite. Only a hash of the link token is stored."""

    __tablename__ = "invite"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.String(254))
    role: Mapped[Role] = mapped_column(enum_column_type(Role, "invite_role"))
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("jurisdiction.id"))
    token_hash: Mapped[str] = mapped_column(sa.String(128), unique=True)
    invited_by: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("app_user.id"))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)


class RefreshToken(Base):
    """Rotating refresh tokens, grouped in a family so reuse of an old token revokes the family."""

    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("app_user.id"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    token_hash: Mapped[str] = mapped_column(sa.String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)


class OtpChallenge(Base):
    """One-time codes for normal-user sign in (mobile or email). Identifier and code are hashed."""

    __tablename__ = "otp_challenge"
    __table_args__ = (sa.Index("ix_otp_challenge_identifier_created", "identifier_hash", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier_hash: Mapped[str] = mapped_column(sa.String(128))
    channel: Mapped[OtpChannel] = mapped_column(enum_column_type(OtpChannel, "otp_channel"))
    code_hash: Mapped[str] = mapped_column(sa.String(128))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    tries: Mapped[int] = mapped_column(default=0, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)
