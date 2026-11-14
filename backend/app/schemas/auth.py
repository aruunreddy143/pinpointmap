from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import Role, UserKind


class RoleGrantOut(BaseModel):
    role: Role
    jurisdiction_id: uuid.UUID


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: UserKind
    email: str | None = None
    roles: list[RoleGrantOut] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    user: UserOut


class SignupRequired(BaseModel):
    signup_token: str


class OtpRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)


class OtpVerify(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6)


class OtpSignup(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    signup_token: str
    name: str = Field(min_length=2, max_length=120)


class StaffLogin(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class StaffTicket(BaseModel):
    ticket: str


class StaffTotp(BaseModel):
    ticket: str
    code: str = Field(min_length=6, max_length=6)


class ForgotPassword(BaseModel):
    email: str = Field(max_length=254)


class ResetPassword(BaseModel):
    token: str
    password: str = Field(max_length=200)


class InviteInfoOut(BaseModel):
    email: str
    role: Role
    totp_secret: str
    totp_uri: str


class AcceptInvite(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(max_length=200)
    totp_code: str = Field(min_length=6, max_length=6)


class CreateInvite(BaseModel):
    email: str = Field(max_length=254)
    role: Role
    jurisdiction_id: uuid.UUID


class InviteCreated(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    expires_at: str
    # Only returned outside production, so a developer can follow the link without an email provider.
    invite_url: str | None = None
