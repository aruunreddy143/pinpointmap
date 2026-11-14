"""Passwords, one-time codes, tokens and authenticator (TOTP) helpers.

- Passwords: argon2id. Identifiers, one-time codes and tokens are stored only as keyed hashes (HMAC).
- Access tokens: short-lived signed JWTs. Refresh tokens are opaque random strings stored hashed.
- TOTP secrets are encrypted at rest (Fernet, key derived from the app secret).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import AuthenticationFailed, InvalidInput
from app.core.settings import get_settings

_ph = PasswordHasher()
# Verifying against this when an account does not exist keeps response time the same.
_DUMMY_HASH = _ph.hash("not-a-real-password")
_JWT_ALG = "HS256"


# ---------- passwords ----------
def password_problem(password: str) -> str | None:
    if len(password) < 10:
        return "Use at least 10 characters."
    if not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password) and re.search(r"\d", password)):
        return "Include upper case, lower case and a number."
    return None


def require_good_password(password: str) -> None:
    problem = password_problem(password)
    if problem:
        raise InvalidInput(problem)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Always does one argon2 verification, even for an unknown account."""
    try:
        return _ph.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


# ---------- keyed hashes ----------
def keyed_hash(purpose: str, value: str) -> str:
    """HMAC-SHA256 of value, namespaced by purpose, so a hash made for one use is useless for another."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# ---------- JWT ----------
class TokenError(AuthenticationFailed):
    pass


def make_jwt(purpose: str, subject: str, minutes: int, **claims: Any) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "purpose": purpose,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        **claims,
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=_JWT_ALG)


def read_jwt(token: str, purpose: str) -> dict[str, Any]:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=[_JWT_ALG])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc
    if data.get("purpose") != purpose:
        raise TokenError("Invalid token")
    return data


# ---------- TOTP ----------
def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_secret_for_invite(token: str) -> str:
    """Derived from the invite token, so no secret needs storing until the invite is accepted."""
    digest = hmac.new(
        get_settings().secret_key.encode(), f"invite-totp:{token}".encode(), hashlib.sha256
    ).digest()
    return base64.b32encode(digest[:20]).decode()


def verify_totp(secret: str, code: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", code)) and pyotp.TOTP(secret).verify(code, valid_window=1)


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="PINPOINT")


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"totp-encryption:{get_settings().secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise AuthenticationFailed("Could not read the stored secret") from exc
