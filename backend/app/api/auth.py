"""Sign-in endpoints. Thin: parse, call the service, return a response model."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import (
    Actor,
    get_client,
    get_notifier,
    get_session,
    rate_limited,
    require_authenticated,
)
from app.core.errors import AuthenticationFailed
from app.core.settings import get_settings
from app.models import AppUser, RoleAssignment
from app.providers.notify import Notifier
from app.schemas.auth import (
    AcceptInvite,
    ForgotPassword,
    InviteInfoOut,
    OtpRequest,
    OtpSignup,
    OtpVerify,
    ResetPassword,
    RoleGrantOut,
    SignupRequired,
    StaffLogin,
    StaffTicket,
    StaffTotp,
    TokenResponse,
    UserOut,
)
from app.services import auth_service
from app.services.audit import ClientInfo

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "pinpoint_refresh"


def _user_out(session: Session, user: AppUser) -> UserOut:
    rows = session.scalars(select(RoleAssignment).where(RoleAssignment.user_id == user.id)).all()
    return UserOut(
        id=user.id,
        name=user.name,
        kind=user.kind,
        email=user.email if user.kind.value == "staff" else None,
        roles=[RoleGrantOut(role=r.role, jurisdiction_id=r.jurisdiction_id) for r in rows],
    )


def _respond_with_tokens(
    session: Session, user: AppUser, pair: auth_service.TokenPair, response: Response
) -> TokenResponse:
    s = get_settings()
    session.commit()
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=s.refresh_token_days * 86400,
        httponly=True,  # not readable by page scripts
        secure=s.environment == "production",
        samesite="strict",
        path="/auth",
    )
    return TokenResponse(
        access_token=pair.access_token, expires_in=pair.expires_in, user=_user_out(session, user)
    )


def _require_csrf_header(x_pinpoint_csrf: str | None) -> None:
    # The refresh cookie is SameSite=Strict; this header adds a second guard against cross-site requests.
    if x_pinpoint_csrf != "1":
        raise AuthenticationFailed("Missing request header.")


# ---------- normal users: one-time code ----------
@router.post("/otp/request", status_code=204, dependencies=[Depends(rate_limited("otp-request", 30, 3600))])
def otp_request(
    body: OtpRequest,
    session: Session = Depends(get_session),
    notifier: Notifier = Depends(get_notifier),
    client: ClientInfo = Depends(get_client),
) -> Response:
    auth_service.request_code(session, body.identifier, notifier, client)
    return Response(status_code=204)


@router.post(
    "/otp/verify",
    response_model=TokenResponse | SignupRequired,
    dependencies=[Depends(rate_limited("otp-verify", 60, 3600))],
)
def otp_verify(
    body: OtpVerify,
    response: Response,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> TokenResponse | SignupRequired:
    result = auth_service.verify_code(session, body.identifier, body.code, client)
    if result.user is None:
        response.status_code = 202  # code is right, but there is no account yet: ask for a name
        assert result.signup_token  # noqa: S101
        return SignupRequired(signup_token=result.signup_token)
    return _respond_with_tokens(
        session, result.user, auth_service.issue_tokens(session, result.user), response
    )


@router.post(
    "/otp/signup", response_model=TokenResponse, dependencies=[Depends(rate_limited("otp-signup", 20, 3600))]
)
def otp_signup(
    body: OtpSignup,
    response: Response,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> TokenResponse:
    user = auth_service.complete_signup(session, body.identifier, body.signup_token, body.name, client)
    return _respond_with_tokens(session, user, auth_service.issue_tokens(session, user), response)


# ---------- staff ----------
@router.post(
    "/staff/login", response_model=StaffTicket, dependencies=[Depends(rate_limited("staff-login", 30, 900))]
)
def staff_login(
    body: StaffLogin,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> StaffTicket:
    return StaffTicket(ticket=auth_service.staff_login(session, body.email, body.password, client))


@router.post(
    "/staff/totp", response_model=TokenResponse, dependencies=[Depends(rate_limited("staff-totp", 30, 900))]
)
def staff_totp(
    body: StaffTotp,
    response: Response,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> TokenResponse:
    user = auth_service.staff_verify_totp(session, body.ticket, body.code, client)
    return _respond_with_tokens(session, user, auth_service.issue_tokens(session, user), response)


# ---------- sessions ----------
@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    x_pinpoint_csrf: str | None = Header(default=None),
) -> TokenResponse:
    _require_csrf_header(x_pinpoint_csrf)
    if not refresh_cookie:
        raise AuthenticationFailed("Please sign in again.")
    user, pair = auth_service.refresh_tokens(session, refresh_cookie, client)
    return _respond_with_tokens(session, user, pair, response)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    session: Session = Depends(get_session),
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    x_pinpoint_csrf: str | None = Header(default=None),
) -> Response:
    _require_csrf_header(x_pinpoint_csrf)
    if refresh_cookie:
        auth_service.logout(session, refresh_cookie)
        session.commit()
    out = Response(status_code=204)
    out.delete_cookie(REFRESH_COOKIE, path="/auth")
    return out


@router.get("/me", response_model=UserOut)
def me(actor: Actor = Depends(require_authenticated), session: Session = Depends(get_session)) -> UserOut:
    return _user_out(session, actor.user)


# ---------- password reset ----------
@router.post("/password/forgot", status_code=204, dependencies=[Depends(rate_limited("pw-forgot", 10, 3600))])
def password_forgot(
    body: ForgotPassword,
    session: Session = Depends(get_session),
    notifier: Notifier = Depends(get_notifier),
    client: ClientInfo = Depends(get_client),
) -> Response:
    auth_service.request_password_reset(session, body.email, notifier, client)
    return Response(status_code=204)


@router.post("/password/reset", status_code=204, dependencies=[Depends(rate_limited("pw-reset", 20, 3600))])
def password_reset(
    body: ResetPassword,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> Response:
    auth_service.reset_password(session, body.token, body.password, client)
    session.commit()
    return Response(status_code=204)


# ---------- staff invites ----------
@router.get(
    "/invites/{token}",
    response_model=InviteInfoOut,
    dependencies=[Depends(rate_limited("invite-get", 60, 3600))],
)
def invite_info(token: str, session: Session = Depends(get_session)) -> InviteInfoOut:
    info = auth_service.get_invite(session, token)
    return InviteInfoOut(
        email=info.email, role=info.role, totp_secret=info.totp_secret, totp_uri=info.totp_uri
    )


@router.post(
    "/invites/{token}/accept",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limited("invite-accept", 20, 3600))],
)
def invite_accept(
    token: str,
    body: AcceptInvite,
    response: Response,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> TokenResponse:
    user = auth_service.accept_invite(session, token, body.name, body.password, body.totp_code, client)
    return _respond_with_tokens(session, user, auth_service.issue_tokens(session, user), response)
