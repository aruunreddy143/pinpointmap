"""Sign-in, tokens, invites and password reset.

Rules (see .claude/skills/pinpoint-rbac-audit):
- Staff: password + authenticator code. Viewers: one-time code by SMS or email.
- A wrong email and a wrong password look identical. "Request code" and "forgot password" answer the
  same whether or not the account exists. Lockouts and attempt limits apply.
- Every sign-in event is audited. Failures are committed before the error is raised.
- Services never import the web framework.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import (
    AccountLocked,
    AuthenticationFailed,
    Conflict,
    InvalidInput,
    NotFound,
    PermissionDenied,
    RateLimited,
)
from app.core.settings import get_settings
from app.domain.identifier import Identifier, parse_identifier
from app.models import AppUser, Invite, OtpChallenge, RefreshToken, RoleAssignment
from app.models.enums import OtpChannel, Role, UserKind
from app.providers.notify import Message, Notifier
from app.services import audit
from app.services.audit import ClientInfo


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True)
class OtpResult:
    user: AppUser | None
    signup_token: str | None = None


@dataclass(frozen=True)
class InviteInfo:
    email: str
    role: Role
    totp_secret: str
    totp_uri: str


# ---------- shared ----------
def _user_by_email(session: Session, email: str, kind: UserKind | None = None) -> AppUser | None:
    stmt = select(AppUser).where(func.lower(AppUser.email) == email.lower())
    if kind:
        stmt = stmt.where(AppUser.kind == kind)
    return session.scalars(stmt).first()


def _fail_login(
    session: Session, user: AppUser | None, who_hash: str, client: ClientInfo, reason: str
) -> None:
    """Count the failure, lock after too many, audit it, and COMMIT so it survives the error."""
    s = get_settings()
    locked = False
    if user:
        user.failed_attempts += 1
        if user.failed_attempts >= s.login_max_failures:
            user.locked_until = _now() + timedelta(minutes=s.lockout_minutes)
            user.failed_attempts = 0
            locked = True
    audit.record(
        session,
        action="auth.login_failed",
        resource_type="user",
        actor_id=user.id if user else None,
        resource_id=str(user.id) if user else None,
        client=client,
        detail={"reason": reason, "who": who_hash[:12], "locked": locked},
    )
    session.commit()
    if locked:
        raise AccountLocked("Too many attempts. Wait a while, or reset your password.")


def _check_not_locked(user: AppUser) -> None:
    if user.locked_until and user.locked_until > _now():
        raise AccountLocked("Too many attempts. Wait a while, or reset your password.")


def issue_tokens(session: Session, user: AppUser, *, family_id: uuid.UUID | None = None) -> TokenPair:
    s = get_settings()
    access = security.make_jwt("access", str(user.id), s.access_token_minutes, kind=user.kind.value)
    refresh = security.new_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=security.keyed_hash("refresh", refresh),
            expires_at=_now() + timedelta(days=s.refresh_token_days),
        )
    )
    session.flush()
    return TokenPair(access, refresh, s.access_token_minutes * 60)


# ---------- staff ----------
def staff_login(session: Session, email: str, password: str, client: ClientInfo) -> str:
    """Step 1: email + password. Returns a short-lived ticket for the authenticator step."""
    who = security.keyed_hash("email", email.strip().lower())
    user = _user_by_email(session, email.strip(), UserKind.STAFF)
    if user and not user.is_active:
        user = None
    if user:
        _check_not_locked(user)
    ok = security.verify_password(password, user.password_hash if user else None)
    if not ok:
        _fail_login(session, user, who, client, "bad_password")
        raise AuthenticationFailed("Email or password is incorrect.")
    assert user is not None  # noqa: S101 (verify_password is False for no account)
    return security.make_jwt("staff_totp", str(user.id), 5)


def staff_verify_totp(session: Session, ticket: str, code: str, client: ClientInfo) -> AppUser:
    """Step 2: the 6-digit authenticator code."""
    data = security.read_jwt(ticket, "staff_totp")
    user = session.get(AppUser, uuid.UUID(data["sub"]))
    if not user or user.kind is not UserKind.STAFF or not user.is_active or not user.totp_secret:
        raise AuthenticationFailed("Sign in again.")
    _check_not_locked(user)
    if not security.verify_totp(security.decrypt_secret(user.totp_secret), code):
        _fail_login(session, user, str(user.id), client, "bad_totp")
        raise AuthenticationFailed("That code is not right. Codes change every 30 seconds.")
    user.failed_attempts = 0
    user.locked_until = None
    audit.record(
        session,
        action="auth.login",
        resource_type="user",
        actor_id=user.id,
        resource_id=str(user.id),
        client=client,
    )
    return user


# ---------- refresh tokens ----------
def refresh_tokens(session: Session, refresh_token: str, client: ClientInfo) -> tuple[AppUser, TokenPair]:
    """Rotate: each refresh token works once. Presenting an old one revokes the whole family."""
    row = session.scalars(
        select(RefreshToken).where(RefreshToken.token_hash == security.keyed_hash("refresh", refresh_token))
    ).first()
    if not row:
        raise AuthenticationFailed("Please sign in again.")
    if row.revoked_at is not None:
        _revoke_family(session, row.family_id)
        audit.record(
            session, action="auth.refresh_reuse", resource_type="user", actor_id=row.user_id, client=client
        )
        session.commit()
        raise AuthenticationFailed("Please sign in again.")
    if row.expires_at <= _now():
        raise AuthenticationFailed("Please sign in again.")
    user = session.get(AppUser, row.user_id)
    if not user or not user.is_active:
        raise AuthenticationFailed("Please sign in again.")
    row.revoked_at = _now()
    return user, issue_tokens(session, user, family_id=row.family_id)


def _revoke_family(session: Session, family_id: uuid.UUID) -> None:
    for t in session.scalars(
        select(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
    ):
        t.revoked_at = _now()


def _revoke_all(session: Session, user_id: uuid.UUID) -> None:
    for t in session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    ):
        t.revoked_at = _now()


def logout(session: Session, refresh_token: str) -> None:
    row = session.scalars(
        select(RefreshToken).where(RefreshToken.token_hash == security.keyed_hash("refresh", refresh_token))
    ).first()
    if row:
        _revoke_family(session, row.family_id)


# ---------- normal users: one-time code by SMS or email ----------
def _identifier_or_error(text: str) -> Identifier:
    ident = parse_identifier(text)
    if not ident:
        raise InvalidInput("Enter a mobile number or an email address.")
    return ident


def request_code(session: Session, identifier_text: str, notifier: Notifier, client: ClientInfo) -> None:
    """Always the same outcome for known and unknown identifiers."""
    s = get_settings()
    ident = _identifier_or_error(identifier_text)
    id_hash = security.keyed_hash("identifier", ident.value)
    recent = session.scalar(
        select(func.count())
        .select_from(OtpChallenge)
        .where(
            OtpChallenge.identifier_hash == id_hash, OtpChallenge.created_at > _now() - timedelta(minutes=15)
        )
    )
    if (recent or 0) >= s.otp_max_requests:
        raise RateLimited("Too many codes requested. Please wait a few minutes and try again.")
    code = security.new_otp_code()
    channel = OtpChannel.SMS if ident.kind == "mobile" else OtpChannel.EMAIL
    session.add(
        OtpChallenge(
            identifier_hash=id_hash,
            channel=channel,
            code_hash=security.keyed_hash(f"otp:{id_hash}", code),
            # Set in Python, not by the database default: Postgres now() is fixed for a whole
            # transaction, which would make "the latest code" ambiguous when two are requested together.
            created_at=_now(),
            expires_at=_now() + timedelta(seconds=s.otp_ttl_seconds),
        )
    )
    session.flush()
    notifier.send(
        Message(
            channel.value,
            ident.value,
            "Your PINPOINT code",
            f"{code} is your PINPOINT code. It expires in 5 minutes.",
        )
    )
    session.commit()


def verify_code(session: Session, identifier_text: str, code: str, client: ClientInfo) -> OtpResult:
    s = get_settings()
    ident = _identifier_or_error(identifier_text)
    id_hash = security.keyed_hash("identifier", ident.value)
    now = _now()
    challenge = session.scalars(
        select(OtpChallenge)
        .where(
            OtpChallenge.identifier_hash == id_hash,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.expires_at > now,
        )
        .order_by(OtpChallenge.created_at.desc())
    ).first()
    if not challenge:
        raise AuthenticationFailed("That code is not valid any more. Request a new one.")
    if challenge.tries >= s.otp_max_tries:
        raise AccountLocked("Too many wrong codes. Request a new code to continue.")
    expected = security.keyed_hash(f"otp:{id_hash}", code.strip())
    if not security.constant_time_equals(expected, challenge.code_hash):
        challenge.tries += 1
        left = s.otp_max_tries - challenge.tries
        audit.record(
            session,
            action="auth.otp_failed",
            resource_type="otp",
            client=client,
            detail={"who": id_hash[:12], "tries_left": left},
        )
        session.commit()
        if left <= 0:
            raise AccountLocked("Too many wrong codes. Request a new code to continue.")
        raise AuthenticationFailed(f"That code is not right. {left} {'try' if left == 1 else 'tries'} left.")
    challenge.consumed_at = now
    user = _find_viewer(session, ident)
    if user is None:
        if ident.kind == "email" and _user_by_email(session, ident.value) is not None:
            session.commit()
            raise AuthenticationFailed("This email can't be used to sign in this way.")
        session.commit()
        return OtpResult(user=None, signup_token=security.make_jwt("signup", id_hash, 10))
    audit.record(
        session,
        action="auth.login",
        resource_type="user",
        actor_id=user.id,
        resource_id=str(user.id),
        client=client,
        detail={"method": ident.kind},
    )
    return OtpResult(user=user)


def _find_viewer(session: Session, ident: Identifier) -> AppUser | None:
    if ident.kind == "email":
        user = _user_by_email(session, ident.value, UserKind.VIEWER)
    else:
        user = session.scalars(
            select(AppUser).where(AppUser.mobile_hash == security.keyed_hash("mobile", ident.value))
        ).first()
    return user if user and user.is_active else None


def complete_signup(
    session: Session, identifier_text: str, signup_token: str, name: str, client: ClientInfo
) -> AppUser:
    ident = _identifier_or_error(identifier_text)
    data = security.read_jwt(signup_token, "signup")
    if data["sub"] != security.keyed_hash("identifier", ident.value):
        raise AuthenticationFailed("Please start again.")
    clean = " ".join(name.split())
    if not 2 <= len(clean) <= 120:
        raise InvalidInput("Please enter your name (2 to 120 characters).")
    user = AppUser(
        kind=UserKind.VIEWER,
        name=clean,
        email=ident.value if ident.kind == "email" else None,
        mobile_hash=security.keyed_hash("mobile", ident.value) if ident.kind == "mobile" else None,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("An account already exists for this mobile number or email. Sign in instead.") from exc
    audit.record(
        session,
        action="auth.signup",
        resource_type="user",
        actor_id=user.id,
        resource_id=str(user.id),
        client=client,
        detail={"method": ident.kind},
    )
    return user


# ---------- staff invites ----------
def create_invite(
    session: Session,
    *,
    actor_user: AppUser,
    actor_can_manage: set[uuid.UUID],
    actor_is_super_admin: bool,
    email: str,
    role: Role,
    jurisdiction_id: uuid.UUID,
    notifier: Notifier,
    client: ClientInfo,
) -> tuple[Invite, str]:
    if jurisdiction_id not in actor_can_manage:
        raise PermissionDenied("You can only invite people to jurisdictions you manage.")
    if role is Role.SUPER_ADMIN and not actor_is_super_admin:
        raise PermissionDenied("You cannot grant a role above your own.")
    email = email.strip().lower()
    parsed = parse_identifier(email)
    if not parsed or parsed.kind != "email":
        raise InvalidInput("Enter a valid work email.")
    if _user_by_email(session, email) is not None:
        raise Conflict("That email already has an account.")
    pending = session.scalars(
        select(Invite).where(
            func.lower(Invite.email) == email, Invite.accepted_at.is_(None), Invite.expires_at > _now()
        )
    ).first()
    if pending:
        raise Conflict("That email already has a pending invite.")
    invite_id = uuid.uuid4()
    token = security.invite_token(invite_id)
    s = get_settings()
    invite = Invite(
        id=invite_id,
        email=email,
        role=role,
        jurisdiction_id=jurisdiction_id,
        token_hash=security.keyed_hash("invite", token),
        invited_by=actor_user.id,
        expires_at=_now() + timedelta(days=s.invite_days),
    )
    session.add(invite)
    session.flush()
    audit.record(
        session,
        action="user.invite",
        resource_type="invite",
        actor_id=actor_user.id,
        resource_id=str(invite.id),
        jurisdiction_id=jurisdiction_id,
        client=client,
        detail={"role": role.value},
    )
    notifier.send(
        Message(
            "email",
            email,
            "You're invited to PINPOINT",
            f"Set up your account: {s.public_base_url}/invite/{token}",
        )
    )
    session.commit()
    return invite, token


def _find_invite(session: Session, token: str) -> Invite:
    invite = session.scalars(
        select(Invite).where(Invite.token_hash == security.keyed_hash("invite", token))
    ).first()
    if not invite or invite.accepted_at is not None or invite.expires_at <= _now():
        raise NotFound("This invite link is invalid or has already been used.")
    return invite


def get_invite(session: Session, token: str) -> InviteInfo:
    invite = _find_invite(session, token)
    secret = security.totp_secret_for_invite(token)
    return InviteInfo(invite.email, invite.role, secret, security.totp_uri(secret, invite.email))


def accept_invite(
    session: Session, token: str, name: str, password: str, totp_code: str, client: ClientInfo
) -> AppUser:
    invite = _find_invite(session, token)
    clean = " ".join(name.split())
    if not 2 <= len(clean) <= 120:
        raise InvalidInput("Please enter your name (2 to 120 characters).")
    security.require_good_password(password)
    secret = security.totp_secret_for_invite(token)
    if not security.verify_totp(secret, totp_code):
        raise InvalidInput("That authenticator code is not right. Check the app and try again.")
    user = AppUser(
        kind=UserKind.STAFF,
        email=invite.email,
        name=clean,
        password_hash=security.hash_password(password),
        totp_secret=security.encrypt_secret(secret),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("That email already has an account.") from exc
    session.add(
        RoleAssignment(
            user_id=user.id,
            role=invite.role,
            jurisdiction_id=invite.jurisdiction_id,
            created_by=invite.invited_by,
        )
    )
    invite.accepted_at = _now()
    audit.record(
        session,
        action="user.invite_accepted",
        resource_type="user",
        actor_id=user.id,
        resource_id=str(user.id),
        jurisdiction_id=invite.jurisdiction_id,
        client=client,
        detail={"role": invite.role.value},
    )
    return user


# ---------- password reset ----------
def request_password_reset(session: Session, email: str, notifier: Notifier, client: ClientInfo) -> None:
    """Always returns normally. A reset link is sent only if a staff account exists."""
    user = _user_by_email(session, email.strip(), UserKind.STAFF)
    if user and user.is_active and user.password_hash:
        s = get_settings()
        token = security.make_jwt(
            "reset", str(user.id), s.reset_minutes, pwf=security.keyed_hash("pw", user.password_hash)[:16]
        )
        notifier.send(
            Message(
                "email",
                user.email or "",
                "Reset your PINPOINT password",
                f"Reset link: {s.public_base_url}/reset/{token}",
            )
        )
        audit.record(
            session,
            action="auth.reset_requested",
            resource_type="user",
            actor_id=user.id,
            resource_id=str(user.id),
            client=client,
        )
    session.commit()


def reset_password(session: Session, token: str, new_password: str, client: ClientInfo) -> None:
    data = security.read_jwt(token, "reset")
    user = session.get(AppUser, uuid.UUID(data["sub"]))
    # The link carries a fingerprint of the current password, so it works once.
    if (
        not user
        or not user.password_hash
        or data.get("pwf") != security.keyed_hash("pw", user.password_hash)[:16]
    ):
        raise AuthenticationFailed("This reset link has expired or was already used.")
    security.require_good_password(new_password)
    user.password_hash = security.hash_password(new_password)
    user.failed_attempts = 0
    user.locked_until = None
    _revoke_all(session, user.id)
    audit.record(
        session,
        action="auth.password_reset",
        resource_type="user",
        actor_id=user.id,
        resource_id=str(user.id),
        client=client,
    )
